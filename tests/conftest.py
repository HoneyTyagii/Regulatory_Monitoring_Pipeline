"""Shared test fixtures for the regulatory monitoring pipeline."""

from __future__ import annotations

import uuid

import pytest

from regmon.config.settings import CrawlSettings, Settings, StorageSettings
from regmon.db import create_database
from regmon.db.engine import Database
from regmon.models import (
    ActionItem,
    ActionPriority,
    DocumentFormat,
    Jurisdiction,
    ParsedDocument,
    RawDocument,
    RiskAssessment,
    RiskLevel,
)


@pytest.fixture()
def db() -> Database:
    """In-memory SQLite database with all tables created."""
    # Import all record modules so Base.metadata knows every table.
    import regmon.approval.store
    import regmon.db.records
    import regmon.dedup.store
    import regmon.notifications.service
    import regmon.pipeline.state  # noqa: F401

    database = create_database("sqlite:///:memory:")
    database.create_all()
    yield database
    database.dispose()


@pytest.fixture()
def settings(tmp_path) -> Settings:
    """Test-friendly settings with temp paths."""
    return Settings(
        crawl=CrawlSettings(rate_limit_per_sec=100, max_retries=1, backoff_factor=0.0),
        storage=StorageSettings(
            raw_storage_path=tmp_path / "raw",
            vectorstore_path=tmp_path / "vs",
        ),
    )


@pytest.fixture()
def raw_document() -> RawDocument:
    """A sample raw document."""
    return RawDocument(
        source_id="rbi-test",
        jurisdiction=Jurisdiction.RBI,
        url="https://rbi.example/doc",
        content="<html><body><h1>KYC Direction</h1><p>All banks must comply with KYC norms.</p></body></html>",
        content_format=DocumentFormat.HTML,
        http_status=200,
    )


@pytest.fixture()
def parsed_document() -> ParsedDocument:
    """A sample parsed document."""
    return ParsedDocument(
        raw_document_id=uuid.uuid4(),
        source_id="rbi-test",
        jurisdiction=Jurisdiction.RBI,
        title="Master Direction on KYC",
        clean_text=(
            "All scheduled commercial banks must implement video-KYC for new "
            "customer onboarding with immediate effect. Non-compliance will "
            "attract penalty of Rs. 5 crore under Banking Regulation Act. "
            "This circular supersedes earlier guidance on the subject."
        ),
        reference_number="RBI/2023-24/115",
        summary="RBI mandates video-KYC for banks.",
    )


@pytest.fixture()
def risk_assessment(parsed_document) -> RiskAssessment:
    """A sample high-risk assessment."""
    return RiskAssessment(
        document_id=parsed_document.id,
        jurisdiction=Jurisdiction.RBI,
        risk_level=RiskLevel.HIGH,
        score=0.65,
        rationale="High risk due to penalty and immediate enforcement.",
        impacted_areas=["Compliance", "Technology"],
    )


@pytest.fixture()
def action_item(risk_assessment) -> ActionItem:
    """A sample action item."""
    return ActionItem(
        assessment_id=risk_assessment.id,
        title="Review KYC circular",
        description="Review and implement video-KYC requirements.",
        priority=ActionPriority.HIGH,
        owner_team="Compliance",
    )
