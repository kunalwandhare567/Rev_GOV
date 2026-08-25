"""
LLM Custom Exceptions.

LLMUnavailableError: raised when the configured provider is unreachable or fails.
  - API layer catches this and returns HTTP 503.
  - NEVER silently fall back to another provider or keyword matching.

LLMConfigError: raised at startup when required API key is missing.
  - This prevents the server from starting.
"""


class LLMUnavailableError(Exception):
    """
    Raised when the configured LLM provider is unreachable or returns an error.

    Correct behavior:
        raise LLMUnavailableError("OpenRouter error")
        → API returns 503: "AI service temporarily unavailable. Please try again."

    NEVER do:
        except LLMUnavailableError:
            return keyword_fallback_response()  # ← FORBIDDEN
    """
    def __init__(self, message: str = "AI service temporarily unavailable. Please try again.", status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LLMConfigError(Exception):
    """
    Raised at startup when LLM_PROVIDER is set but the required API key is missing
    or invalid. This prevents the server from starting with a clear error message.
    """
    pass
