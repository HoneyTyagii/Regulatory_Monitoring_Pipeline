"""Multi-agent orchestrator: the full pipeline graph.

Wires the agents into a sequential processing graph::

    Crawler → Parser → Normalize → Dedup → Classify → Summarize
        → Index → Risk Assess → Action Plan → (Notify)

Each stage is error-isolated: a failure on one document logs the error and
continues with the next. The orchestrator tracks progress in
:class:`~regmon.pipeline.state.PipelineMemory` so it can skip already-processed
documents on subsequent runs.
"""

from __future__ import annotations

import uuid

from regmon.actions.planner import ActionPlannerAgent
from regmon.classification import ClassificationAgent
from regmon.config.settings import Settings
from regmon.crawler import CrawlerAgent
from regmon.crawler.adapters import AdapterRegistry, default_registry
from regmon.crawler.storage import StoredDocument
from regmon.db.audit import AuditEventType, AuditLog
from regmon.db.document_store import DocumentStore
from regmon.db.engine import Database
from regmon.dedup import DeduplicationEngine, DuplicateKind, SqlFingerprintIndex
from regmon.embeddings import DocumentIndexer, build_indexer
from regmon.logging_config import get_logger
from regmon.models import ParsedDocument, RegulatorySource
from regmon.normalize import ContentCleaner
from regmon.parser import DocumentParserAgent, ParseError
from regmon.pipeline.context import DocumentContext, PipelineRunContext
from regmon.pipeline.state import PipelineMemory, PipelineStage
from regmon.rag import RAGSearchService
from regmon.risk import RiskAssessmentAgent
from regmon.summarization import SummarizationAgent, create_llm_client

log = get_logger(__name__)


class PipelineOrchestrator:
    """Orchestrates the full regulatory monitoring pipeline.

    All agents and stores are injectable for testing; omitted dependencies are
    built from ``settings``.
    """

    def __init__(
        self,
        settings: Settings,
        db: Database,
        *,
        crawler: CrawlerAgent | None = None,
        adapters: AdapterRegistry | None = None,
        parser: DocumentParserAgent | None = None,
        cleaner: ContentCleaner | None = None,
        dedup: DeduplicationEngine | None = None,
        classifier: ClassificationAgent | None = None,
        summarizer: SummarizationAgent | None = None,
        indexer: DocumentIndexer | None = None,
        risk_agent: RiskAssessmentAgent | None = None,
        planner: ActionPlannerAgent | None = None,
        document_store: DocumentStore | None = None,
        audit_log: AuditLog | None = None,
        memory: PipelineMemory | None = None,
    ) -> None:
        self._settings = settings
        self._db = db
        self._adapters = adapters or default_registry()
        self._crawler = crawler or CrawlerAgent(settings, adapters=self._adapters)
        self._parser = parser or DocumentParserAgent()
        self._cleaner = cleaner or ContentCleaner()
        self._dedup = dedup or DeduplicationEngine(SqlFingerprintIndex(db))
        self._classifier = classifier or ClassificationAgent()
        self._summarizer = summarizer or SummarizationAgent(create_llm_client(settings))
        self._indexer = indexer or build_indexer(settings)
        self._rag = RAGSearchService(self._indexer)
        self._risk_agent = risk_agent or RiskAssessmentAgent(rag_service=self._rag)
        self._planner = planner or ActionPlannerAgent()
        self._store = document_store or DocumentStore(db)
        self._audit = audit_log or AuditLog(db)
        self._memory = memory or PipelineMemory(db)

    async def run(self, sources: list[RegulatorySource]) -> PipelineRunContext:
        """Execute a full pipeline run across the given sources."""
        run_id = str(uuid.uuid4())[:8]
        ctx = PipelineRunContext(run_id=run_id)
        log.info("pipeline.run_started", run_id=run_id, sources=len(sources))

        # Stage 1: Crawl
        stored_docs = await self._crawl(sources)
        log.info("pipeline.crawled", run_id=run_id, documents=len(stored_docs))

        # Stage 2-N: Process each document through the graph
        for stored in stored_docs:
            doc_ctx = DocumentContext(raw=stored.document)
            try:
                self._process_document(doc_ctx, run_id)
            except Exception as exc:
                doc_ctx.error = str(exc)
                ctx.errors.append((doc_ctx.document_id, str(exc)))
                log.warning(
                    "pipeline.document_failed", document_id=doc_ctx.document_id, error=str(exc)
                )
            ctx.documents.append(doc_ctx)

        log.info(
            "pipeline.run_completed",
            run_id=run_id,
            total=len(ctx.documents),
            processed=ctx.processed_count,
            duplicates=ctx.duplicate_count,
            errors=ctx.error_count,
        )
        return ctx

    async def _crawl(self, sources: list[RegulatorySource]) -> list[StoredDocument]:
        """Crawl all sources, returning stored raw documents."""
        return await self._crawler.crawl(sources)

    def _process_document(self, ctx: DocumentContext, run_id: str) -> None:
        """Run a single document through all processing stages."""
        doc_id = ctx.document_id

        # Skip if already fully processed in a prior run
        if self._memory.has_completed(doc_id, PipelineStage.ACTIONS_PLANNED):
            ctx.is_duplicate = True
            return

        # Persist raw
        self._store.add_raw(ctx.raw)
        self._memory.mark_completed(doc_id, PipelineStage.FETCHED, run_id)
        self._audit.record(
            AuditEventType.DOCUMENT_FETCHED,
            entity_type="raw_document",
            entity_id=doc_id,
            actor="crawler",
        )

        # Parse
        parsed = self._parse(ctx)
        if parsed is None:
            return
        ctx.parsed = parsed
        self._memory.mark_completed(doc_id, PipelineStage.PARSED, run_id)

        # Normalize
        ctx.parsed = self._cleaner.normalize_document(parsed)
        self._memory.mark_completed(doc_id, PipelineStage.NORMALIZED, run_id)

        # Dedup
        dedup_result = self._dedup.check_and_add(doc_id, ctx.parsed.clean_text)
        if dedup_result.kind != DuplicateKind.UNIQUE:
            ctx.is_duplicate = True
            self._memory.mark_completed(doc_id, PipelineStage.DEDUPLICATED, run_id)
            log.info("pipeline.duplicate_skipped", document_id=doc_id, kind=dedup_result.kind.value)
            return
        self._memory.mark_completed(doc_id, PipelineStage.DEDUPLICATED, run_id)

        # Persist parsed
        self._store.add_parsed(ctx.parsed)
        self._audit.record(
            AuditEventType.DOCUMENT_PARSED,
            entity_type="parsed_document",
            entity_id=str(ctx.parsed.id),
            actor="parser",
        )

        # Classify
        cls_result = self._classifier.classify(ctx.parsed)
        ctx.classification = cls_result
        self._memory.mark_completed(doc_id, PipelineStage.CLASSIFIED, run_id)
        self._audit.record(
            AuditEventType.DOCUMENT_CLASSIFIED,
            entity_type="parsed_document",
            entity_id=str(ctx.parsed.id),
            actor="classifier",
            payload={"primary_topic": cls_result.classification.primary_topic},
        )

        # Summarize
        patched, summ_result = self._summarizer.summarize_and_patch(ctx.parsed)
        ctx.parsed = patched
        ctx.summarization = summ_result
        self._memory.mark_completed(doc_id, PipelineStage.SUMMARIZED, run_id)

        # Index for RAG
        self._indexer.index_document(ctx.parsed)
        self._memory.mark_completed(doc_id, PipelineStage.INDEXED, run_id)

        # Risk assessment
        assessment = self._risk_agent.assess(ctx.parsed, cls_result.classification)
        ctx.risk_assessment = assessment
        self._memory.mark_completed(doc_id, PipelineStage.RISK_ASSESSED, run_id)
        self._audit.record(
            AuditEventType.RISK_ASSESSED,
            entity_type="risk_assessment",
            entity_id=str(assessment.id),
            actor="risk_agent",
            payload={"risk_level": assessment.risk_level.value, "score": assessment.score},
        )

        # Action planning
        items = self._planner.plan(ctx.parsed, assessment, cls_result.classification)
        ctx.action_items = items
        self._memory.mark_completed(doc_id, PipelineStage.ACTIONS_PLANNED, run_id)
        for item in items:
            self._audit.record(
                AuditEventType.ACTION_CREATED,
                entity_type="action_item",
                entity_id=str(item.id),
                actor="planner",
                payload={"title": item.title, "priority": item.priority.value},
            )

    def _parse(self, ctx: DocumentContext) -> ParsedDocument | None:
        """Parse the raw document, returning None on failure."""
        try:
            return self._parser.parse(ctx.raw)
        except ParseError as exc:
            ctx.error = str(exc)
            log.warning("pipeline.parse_failed", document_id=ctx.document_id, error=str(exc))
            return None


__all__ = ["PipelineOrchestrator"]
