# ============================================================
# ai_factory.py — AI service factory
# ============================================================
# Returns the right AI service based on config.
# Makes it easy to swap between Groq (cloud) and Ollama (local).
# ============================================================

from app.core.config import AI_PROVIDER


def get_ai_chat_service():
    """
    Returns the configured AI chat service.
    Reads AI_PROVIDER from config to decide.
    """
    if AI_PROVIDER == "ollama":
        from app.services.ai_chat_ollama import OllamaChatService
        return OllamaChatService()
    else:
        from app.services.ai_chat import AIChatService
        return AIChatService()