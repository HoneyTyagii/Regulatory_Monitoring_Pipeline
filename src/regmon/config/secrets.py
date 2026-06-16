"""Helpers for safely handling sensitive configuration values.

Secrets are stored as :class:`pydantic.SecretStr` throughout the settings
models, which prevents accidental disclosure via ``repr``/logging. This module
provides the small, explicit surface for revealing a secret at the point of use
and for masking values when they must appear in human-facing output.
"""

from __future__ import annotations

from pydantic import SecretStr


def reveal(secret: SecretStr | None) -> str | None:
    """Return the underlying secret value, or ``None`` if unset.

    Call this only at the boundary where the raw value is actually needed
    (e.g. constructing an HTTP client), never for logging or display.
    """
    if secret is None:
        return None
    return secret.get_secret_value()


def require(secret: SecretStr | None, name: str) -> str:
    """Reveal a secret that must be present, raising if it is missing.

    Parameters
    ----------
    secret:
        The secret to reveal.
    name:
        Human-readable name used in the error message (e.g. ``"OPENAI_API_KEY"``).
    """
    value = reveal(secret)
    if not value:
        raise ValueError(f"required secret is not configured: {name}")
    return value


def mask(value: str | SecretStr | None, *, show: int = 4) -> str:
    """Return a masked representation safe to log or display.

    Keeps the last ``show`` characters visible and replaces the rest with
    asterisks. Short or empty values are fully masked.

    >>> mask("sk-1234567890")
    '*********7890'
    """
    raw = reveal(value) if isinstance(value, SecretStr) else value
    if not raw:
        return ""
    if show <= 0 or len(raw) <= show:
        return "*" * len(raw)
    return "*" * (len(raw) - show) + raw[-show:]


__all__ = ["mask", "require", "reveal"]
