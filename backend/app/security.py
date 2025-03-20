"""Security helpers: secret redaction, path safety, request fingerprinting.

The redaction helpers are used by providers, reports, logs and the API so a
credential can never leak into a log line, an export file or the dashboard.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path

_REDACTED = "***REDACTED***"

# Keys whose *values* are secret wherever they appear in a dict.
SECRET_KEYS = {
    "api_key",
    "apikey",
    "api-key",
    "authorization",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "x-api-key",
    "openai_api_key",
    "anthropic_api_key",
    "hf_token",
    "bearer",
}

_Replacement = str | Callable[[re.Match[str]], str]
_PATTERNS: tuple[tuple[re.Pattern[str], _Replacement], ...] = (
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"), _REDACTED),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{8,}\b"), _REDACTED),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), _REDACTED),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{10,}"), "Bearer " + _REDACTED),
    (re.compile(r'(?i)"(api[_-]?key|token|secret|password)"\s*:\s*"[^"]{4,}"'), r'"\1": "' + _REDACTED + '"'),
    (
        re.compile(r"(?i)\b(api[_-]?key|apikey|token|secret|password)\s*[=:]\s*['\"]?([^\s'\"&,;]{4,})"),
        lambda m: f"{m.group(1)}={_REDACTED}",
    ),
)


def redact_text(text: str, extra_secrets: list[str] | None = None) -> str:
    """Remove known secret shapes and any explicitly supplied secret values."""
    out = text or ""
    for secret in extra_secrets or []:
        if secret and len(secret) >= 4:
            out = out.replace(secret, _REDACTED)
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def redact_obj(obj: object, extra_secrets: list[str] | None = None, _depth: int = 0) -> object:
    """Recursively redact secret-looking values in a JSON-compatible structure."""
    if _depth > 12:
        return obj
    if isinstance(obj, dict):
        out: dict = {}
        for key, value in obj.items():
            if isinstance(key, str) and key.lower() in SECRET_KEYS:
                out[key] = _REDACTED if value not in (None, "", False) else value
            else:
                out[key] = redact_obj(value, extra_secrets, _depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v, extra_secrets, _depth + 1) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj, extra_secrets)
    return obj


def mask_key(key: str | None) -> str:
    """Human-readable mask: never reveals more than the last 4 characters."""
    if not key:
        return ""
    if len(key) <= 4:
        return "*" * len(key)
    return "*" * 4 + key[-4:]


def safe_join(root: Path, *parts: str) -> Path:
    """Join ``parts`` under ``root`` and guarantee the result stays inside it.

    Guards against path traversal (``../``) and absolute-path escapes in
    user-supplied document/file names.
    """
    root_resolved = root.resolve()
    candidate = root_resolved
    for part in parts:
        part = str(part)
        if not part or part in (".",):
            continue
        if Path(part).is_absolute() or part.startswith("\\") or re.match(r"^[A-Za-z]:", part):
            raise ValueError(f"absolute path not allowed: {part!r}")
        candidate = candidate / part
    resolved = candidate.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError("path escapes the allowed root directory")
    return resolved


def sanitize_filename(name: str, fallback: str = "upload") -> str:
    """Reduce an arbitrary user string to a safe single path component."""
    base = Path((name or "").replace("\\", "/")).name.strip()
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    if not base or base in (".", ".."):
        return fallback
    return base[:120]


def fingerprint(text: str) -> str:
    """Stable short content fingerprint (used for corpus drift detection)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def constant_time_equals(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest((a or "").encode(), (b or "").encode())
