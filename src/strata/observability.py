"""Datadog LLM Observability bootstrap.

Enables Datadog LLM Observability in *agentless* mode so that every OpenAI /
Anthropic / CrewAI / openai-agents call this app makes is captured as a span and
shipped to Datadog -- no Datadog Agent process required. It is a no-op unless
``DD_LLMOBS_ENABLED`` is truthy, so local development, tests and CI are
unaffected, and it degrades gracefully (a warning, not a crash) if ``ddtrace``
is not installed.

Enable it by setting these environment variables in your deployment:

    DD_LLMOBS_ENABLED=1
    DD_API_KEY=<your Datadog API key>
    DD_SITE=us5.datadoghq.com          # must match your Datadog org's site
    DD_LLMOBS_ML_APP=<app name>        # optional; overrides the per-app default

Then run the app normally. Requires ``ddtrace`` (already added to this project's
dependencies). The ml_app name is what the AgentOps dashboard groups traces by
in its "By App" breakdown.
"""

from __future__ import annotations

import logging
import os

_log = logging.getLogger("observability")
_initialized = False


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def init_observability(default_ml_app: str = "agent-app") -> bool:
    """Enable Datadog LLM Observability once, if ``DD_LLMOBS_ENABLED`` is set.

    ``default_ml_app`` is used when ``DD_LLMOBS_ML_APP`` is not set in the
    environment. Returns ``True`` if observability was activated, else ``False``.
    """
    global _initialized
    if _initialized:
        return True
    if not _truthy(os.getenv("DD_LLMOBS_ENABLED")):
        return False
    try:
        from ddtrace.llmobs import LLMObs
    except ImportError:
        _log.warning(
            "ddtrace is not installed -- LLM Observability disabled. "
            "Install it with: pip install 'ddtrace>=2.8'"
        )
        return False

    LLMObs.enable(
        ml_app=os.getenv("DD_LLMOBS_ML_APP") or default_ml_app,
        agentless_enabled=True,
    )
    _initialized = True
    _log.info("Datadog LLM Observability enabled (agentless).")
    return True
