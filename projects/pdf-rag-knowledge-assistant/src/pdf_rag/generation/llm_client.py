"""
LLM generation client with provider abstraction and retry logic.

Supports OpenAI and Anthropic behind a single interface, selected via
PRIMARY_LLM_PROVIDER, so the rest of the app is provider-agnostic.
"""

from anthropic import Anthropic
from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from pdf_rag.config import Settings
from pdf_rag.core.exceptions import GenerationError
from pdf_rag.core.logging_config import get_logger
from pdf_rag.generation.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from pdf_rag.retrieval.retriever import RetrievedChunk

logger = get_logger(__name__)

RETRYABLE_EXCEPTIONS = (TimeoutError, ConnectionError)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
)
def _call_openai(settings: Settings, user_prompt: str) -> str:
    if not settings.openai_api_key:
        raise GenerationError("OPENAI_API_KEY is not configured.")
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
)
def _call_anthropic(settings: Settings, user_prompt: str) -> str:
    if not settings.anthropic_api_key:
        raise GenerationError("ANTHROPIC_API_KEY is not configured.")
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_chat_model,
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text"))


def generate_answer(question: str, chunks: list[RetrievedChunk], settings: Settings) -> str:
    """
    Generate a grounded answer from retrieved chunks.

    Raises:
        GenerationError: if the LLM call fails after retries, or the
        provider is not configured.
    """
    user_prompt = build_user_prompt(question, chunks)

    try:
        if settings.primary_llm_provider == "openai":
            answer = _call_openai(settings, user_prompt)
        elif settings.primary_llm_provider == "anthropic":
            answer = _call_anthropic(settings, user_prompt)
        else:
            raise GenerationError(f"Unsupported LLM provider: {settings.primary_llm_provider}")
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError(f"LLM generation failed: {exc}") from exc

    logger.info("generation_complete", provider=settings.primary_llm_provider, chunks_used=len(chunks))
    return answer
