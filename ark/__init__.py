"""Endpoint resolution, the HTTP client, and the error text a user actually reads."""
from __future__ import annotations

from .client import ArkClient
from .config import (
    AGENT_PLAN_BASE_URL,
    ARK,
    CUSTOM,
    OPENAI,
    STANDARD_BASE_URL,
    Endpoint,
    ark_endpoints,
    defaults,
    openai_endpoints,
    profile_names,
    resolve,
)
from .errors import ArkError, explain, task_failure

__all__ = [
    "AGENT_PLAN_BASE_URL",
    "ARK",
    "ArkClient",
    "ArkError",
    "CUSTOM",
    "Endpoint",
    "OPENAI",
    "STANDARD_BASE_URL",
    "ark_endpoints",
    "defaults",
    "explain",
    "openai_endpoints",
    "profile_names",
    "resolve",
    "task_failure",
]
