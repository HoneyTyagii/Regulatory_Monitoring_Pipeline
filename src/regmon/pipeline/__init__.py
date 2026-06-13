"""Multi-agent pipeline orchestrator.

Wires the full processing graph: crawl → parse → normalize → dedup → classify
→ summarize → index → risk assess → action plan, with persistent state tracking
for resumption across runs.

>>> from regmon.pipeline import PipelineOrchestrator
>>> orchestrator = PipelineOrchestrator(settings, db)
>>> result = await orchestrator.run(sources)
"""

from __future__ import annotations

from regmon.pipeline.context import DocumentContext, PipelineRunContext
from regmon.pipeline.orchestrator import PipelineOrchestrator
from regmon.pipeline.state import PipelineMemory, PipelineStage, PipelineStateRecord

__all__ = [
    "DocumentContext",
    "PipelineMemory",
    "PipelineOrchestrator",
    "PipelineRunContext",
    "PipelineStage",
    "PipelineStateRecord",
]
