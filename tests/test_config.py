"""Tests for configuration and settings management."""

from __future__ import annotations

from pydantic import SecretStr

from regmon.config import (
    SourceRegistry,
    load_settings,
    mask,
    require,
    reveal,
)
from regmon.config.settings import Environment


class TestSettings:
    def test_load_from_env(self) -> None:
        env = {"REGMON_ENV": "production", "REGMON_DRY_RUN": "false"}
        settings = load_settings(env_file=None, environ=env)
        assert settings.app.env == Environment.PRODUCTION
        assert settings.app.dry_run is False

    def test_empty_env_values_ignored(self) -> None:
        env = {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}
        settings = load_settings(env_file=None, environ=env)
        assert settings.llm.openai_api_key is None
        assert settings.llm.openai_model == "gpt-4o-mini"  # default preserved

    def test_overrides_take_precedence(self) -> None:
        settings = load_settings(
            env_file=None,
            environ={},
            overrides={"app": {"log_level": "DEBUG"}},
        )
        assert settings.app.log_level == "DEBUG"


class TestSecrets:
    def test_reveal_none(self) -> None:
        assert reveal(None) is None

    def test_reveal_value(self) -> None:
        assert reveal(SecretStr("secret123")) == "secret123"

    def test_require_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            require(None, "OPENAI_API_KEY")

    def test_mask(self) -> None:
        assert mask("sk-1234567890") == "*********7890"
        assert mask(SecretStr("abc")) == "***"


class TestSourceRegistry:
    def test_default_registry_loads(self) -> None:
        reg = SourceRegistry.default()
        assert len(reg) >= 4

    def test_for_jurisdiction(self) -> None:
        from regmon.models import Jurisdiction

        reg = SourceRegistry.default()
        rbi = reg.for_jurisdiction(Jurisdiction.RBI)
        assert len(rbi) >= 1
        assert all(s.jurisdiction == Jurisdiction.RBI for s in rbi)

    def test_duplicate_ids_rejected(self) -> None:
        import pytest

        from regmon.models import Jurisdiction, RegulatorySource, SourceType

        src = RegulatorySource(
            id="dup",
            name="D",
            jurisdiction=Jurisdiction.RBI,
            url="https://x.com",
            source_type=SourceType.HTML,
        )
        with pytest.raises(ValueError, match="duplicate"):
            SourceRegistry([src, src])
