"""Default AI provider adapter — Google Gemini (SRS v1.2 Sec.7; Detailed
Design v0.3 Sec.5.5/5.6). Implements both capability interfaces behind the
same vendor for v1, per the "single default provider" decision.

Swapping only one side later (e.g., embeddings to Voyage AI) means writing a
new adapter for that one interface and pointing AI_EMBEDDING_PROVIDER at it
(Sec.5.6, practice #3) — this class does not need to change.
"""
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.services.ai_service.dtos import (
    ChatRequest,
    ChatResponse,
    ChatRole,
    EmbedRequest,
    EmbedResponse,
    ProviderCapabilities,
)
from app.services.ai_service.interfaces import (
    ChatProvider,
    EmbeddingProvider,
    ProviderAuthError,
    ProviderContentPolicyError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

_CAPABILITIES = ProviderCapabilities(
    streaming=True,
    context_caching=True,
    multimodal_embeddings=False,  # set True if/when switched to gemini-embedding-2
)


class GeminiAdapter(ChatProvider, EmbeddingProvider):
    def __init__(self, api_key: str, chat_model: str, embedding_model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._chat_model = chat_model
        self._embedding_model = embedding_model

    @property
    def capabilities(self) -> ProviderCapabilities:
        return _CAPABILITIES

    async def generate(self, request: ChatRequest) -> ChatResponse:
        system_parts = [m.content for m in request.messages if m.role == ChatRole.SYSTEM]
        turns = [
            genai_types.Content(
                role="user" if m.role == ChatRole.USER else "model",
                parts=[genai_types.Part.from_text(text=m.content)],
            )
            for m in request.messages
            if m.role != ChatRole.SYSTEM
        ]
        try:
            response = await self._client.aio.models.generate_content(
                model=self._chat_model,
                contents=turns,  # type: ignore[arg-type]  # list invariance false positive, see embed() below
                config=genai_types.GenerateContentConfig(
                    system_instruction="\n".join(system_parts) or None,
                    max_output_tokens=request.max_output_tokens,
                    temperature=request.temperature,
                ),
            )
        except genai_errors.ClientError as exc:  # 4xx: auth, rate limit, content policy
            raise _map_client_error(exc) from exc
        except TimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc

        usage = response.usage_metadata
        return ChatResponse(
            content=response.text or "",
            finish_reason=_first_finish_reason(response),
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
        )

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        try:
            response = await self._client.aio.models.embed_content(
                model=self._embedding_model,
                contents=list(request.texts),  # type: ignore[arg-type]  # list[str] is a valid
                # runtime value for `contents`; mypy flags it due to List invariance against the
                # SDK's broader Union type, not an actual type mismatch.
            )
        except genai_errors.ClientError as exc:
            raise _map_client_error(exc) from exc
        except TimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc

        embeddings = response.embeddings or []
        vectors: list[list[float]] = []
        for e in embeddings:
            if e.values is None:
                raise ProviderError("Gemini returned an embedding with no values")
            vectors.append(e.values)
        dimension = len(vectors[0]) if vectors else 0
        return EmbedResponse(vectors=vectors, dimension=dimension)


def _first_finish_reason(response: genai_types.GenerateContentResponse) -> str:
    candidates = response.candidates or []
    if candidates and candidates[0].finish_reason:
        return str(candidates[0].finish_reason)
    return "stop"


def _map_client_error(exc: genai_errors.ClientError) -> ProviderError:
    """Normalize Gemini's ClientError into the shared provider-error
    hierarchy (Sec.5.6, practice #5) so retry/fallback logic (NFR-005,
    SRS Sec.9) never has to branch on the Gemini SDK specifically."""
    status = exc.code
    if status in (401, 403):
        return ProviderAuthError(str(exc))
    if status == 429:
        return ProviderRateLimitError(str(exc))
    if status == 400 and "safety" in str(exc).lower():
        return ProviderContentPolicyError(str(exc))
    return ProviderError(str(exc))
