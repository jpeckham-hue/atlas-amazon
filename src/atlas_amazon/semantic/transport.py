"""Transports: how a semantic request reaches a model, or a recording of one.

A request is a plain dict of Messages API parameters (model, max_tokens,
system, messages, output_config, ...). It never contains credentials. A
`TransportResponse` is a normalized view of the reply, plus a raw dump for
audit.

* `AnthropicTransport`: **live**. It uses the official `anthropic` SDK
  (optional dependency: `pip install atlas-amazon[llm]`), imported lazily.
  Credentials come only from the environment or an `ant auth login`
  profile; atlas never reads, stores or logs them. Live calls are disabled
  unless `ATLAS_ALLOW_LIVE_LLM=1` is set or `allow_live=True` is passed, so
  tests and CI can't call the network by accident.
* `ScriptedTransport`: deterministic responses from a Python function, for
  tests and synthetic recordings.
* `RecordingTransport`: wraps a transport and appends every exchange to a
  recording file.
* `ReplayTransport`: answers only from a recording, matched by request hash.
  A request that isn't in the recording raises `ReplayMiss`. It never
  touches the network.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from atlas_amazon.jsonvalue import canonical_json, thaw
from atlas_amazon.semantic.records import ChecksummedJsonl, ensure_no_secrets

LIVE_ENV_FLAG = "ATLAS_ALLOW_LIVE_LLM"
DEFAULT_FALLBACK_BETA = "server-side-fallback-2026-07-01"


def request_hash(request: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()


class TransportError(Exception):
    pass


class LiveCallsDisabled(TransportError):
    pass


class ReplayMiss(TransportError):
    pass


@dataclass(frozen=True, slots=True)
class TransportResponse:
    id: str
    model: str  # the model that actually served the request
    stop_reason: str | None
    text: str | None  # first text block (structured JSON), if any
    usage: Mapping[str, Any] = field(default_factory=dict)
    responded_at: str = ""  # ISO 8601 timestamp of the original response
    transport: str = "unknown"  # where the response originally came from
    synthetic: bool = False  # True for scripted/fabricated responses

    def to_dict(self) -> dict[str, Any]:
        return thaw(asdict(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TransportResponse:
        return cls(**dict(data))


@runtime_checkable
class Transport(Protocol):
    name: str
    is_live: bool  # counts against live-call limits

    def send(self, request: Mapping[str, Any]) -> TransportResponse: ...


class AnthropicTransport:
    """Live Claude API calls through the official SDK (lazily imported)."""

    name = "anthropic"
    is_live = True

    def __init__(
        self,
        *,
        client: Any = None,
        allow_live: bool | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._allow = allow_live
        self._clock = clock or (lambda: datetime.now(UTC))

    def _ensure_client(self) -> Any:
        allowed = self._allow if self._allow is not None else os.environ.get(LIVE_ENV_FLAG) == "1"
        if not allowed:
            raise LiveCallsDisabled(
                f"live LLM calls are disabled; set {LIVE_ENV_FLAG}=1 (or allow_live=True) "
                f"to enable them"
            )
        if self._client is None:
            try:
                import anthropic  # optional dependency, imported only for live use
            except ImportError as exc:  # pragma: no cover - environment-specific
                raise TransportError(
                    "install the 'llm' extra: pip install 'atlas-amazon[llm]'"
                ) from exc
            self._client = anthropic.Anthropic()  # credentials resolved by the SDK
        return self._client

    def send(self, request: Mapping[str, Any]) -> TransportResponse:
        client = self._ensure_client()
        params = thaw(request)
        if "betas" in params:
            message = client.beta.messages.create(**params)
        else:
            message = client.messages.create(**params)
        text = next((b.text for b in message.content if getattr(b, "type", "") == "text"), None)
        usage = getattr(message, "usage", None)
        usage_dict = (
            {
                name: getattr(usage, name, None)
                for name in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
            }
            if usage is not None
            else {}
        )
        return TransportResponse(
            id=message.id,
            model=message.model,
            stop_reason=message.stop_reason,
            text=text,
            usage=usage_dict,
            responded_at=self._clock().isoformat(),
            transport=self.name,
        )


class ScriptedTransport:
    """Deterministic responses for tests and synthetic recordings. Never networked."""

    name = "scripted"

    def __init__(
        self, responder: Callable[[Mapping[str, Any]], TransportResponse], *, is_live: bool = True
    ) -> None:
        self._responder = responder
        self.is_live = is_live  # True lets tests exercise live-call limits
        self.requests: list[dict[str, Any]] = []

    def send(self, request: Mapping[str, Any]) -> TransportResponse:
        self.requests.append(thaw(request))
        return self._responder(request)


class RecordingTransport:
    """Pass-through that appends every request/response exchange to a recording file."""

    def __init__(self, inner: Transport, path: str | os.PathLike[str]) -> None:
        self.inner = inner
        self.name = inner.name
        self.is_live = inner.is_live
        self._file = ChecksummedJsonl(path)

    def send(self, request: Mapping[str, Any]) -> TransportResponse:
        response = self.inner.send(request)
        record = {
            "request_hash": request_hash(request),
            "request": thaw(request),
            "response": response.to_dict(),
        }
        ensure_no_secrets(record, "recording")
        self._file.append([record])
        return response


class ReplayTransport:
    """Serves recorded responses by exact request hash. Never calls the network."""

    name = "replay"
    is_live = False

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = path
        self._responses: dict[str, TransportResponse] = {}
        for record in ChecksummedJsonl(path).read():
            if request_hash(record["request"]) != record["request_hash"]:
                raise TransportError(f"{path}: recorded request does not match its hash")
            self._responses.setdefault(
                record["request_hash"], TransportResponse.from_dict(record["response"])
            )

    def __len__(self) -> int:
        return len(self._responses)

    def send(self, request: Mapping[str, Any]) -> TransportResponse:
        key = request_hash(request)
        try:
            return self._responses[key]
        except KeyError:
            raise ReplayMiss(f"no recorded response for request {key}") from None
