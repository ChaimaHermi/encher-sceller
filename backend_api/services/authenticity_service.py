"""
Service d'authenticité — appelle l'agent image_validation_agent.
"""
import os
import asyncio
import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)


def _run_agent_sync(image_path: str, category: str | None, description: str | None) -> dict[str, Any]:
    """Exécution synchrone de l'agent (bloquant)."""
    from backend_ai.agents.image_validation_agent import GeminiAutonomousAgent

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    serpapi_key = os.getenv("SERPAPI_KEY")
    imgbb_api_key = os.getenv("IMGBB_API_KEY") or "dummy"
    serper_api_key = os.getenv("SERPER_API_KEY")
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY manquant dans .env")
    if not serpapi_key:
        raise ValueError("SERPAPI_KEY manquant dans .env")

    agent = GeminiAutonomousAgent(
        gemini_api_key=gemini_api_key,
        serpapi_key=serpapi_key,
        imgbb_api_key=imgbb_api_key,
        serper_api_key=serper_api_key,
        openrouter_api_key=openrouter_api_key,
    )
    try:
        return agent.run(image_path, category=category, description=description)
    except Exception as e:
        logger.error("Agent authenticity failed: %s\n%s", e, traceback.format_exc())
        raise RuntimeError(f"Erreur agent authenticité: {type(e).__name__}: {e}") from e


def _to_serializable(obj: Any) -> Any:
    """Convertit un objet en structure JSON-serialisable."""
    if obj is None:
        return None
    if hasattr(obj, "__dict__") and not isinstance(obj, dict):
        return _to_serializable(vars(obj))
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


async def run_authenticity_analysis(
    image_path: str,
    category: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """
    Lance l'analyse d'authenticité en arrière-plan (ne bloque pas l'event loop).
    Retourne un dict JSON-serialisable.
    """
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: _run_agent_sync(image_path, category, description),
        )
        return _to_serializable(result)
    except Exception as e:
        logger.exception("run_authenticity_analysis failed")
        raise
