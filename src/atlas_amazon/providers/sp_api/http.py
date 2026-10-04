"""HTTP transports for Amazon market-data APIs: live, recording, replay, scripted.

The same discipline as the semantic transports (`semantic.transport`):

* An `HttpRequest` is method + base URL + path + sorted query parameters. It
  never contains credentials, so its hash is stable and it can be recorded.
* `LiveSpApiTransport` is the only class that touches the network. It is
  **disabled** unless `ATLAS_ALLOW_LIVE_MARKET=1` (or `allow_live=True`), a
  separate opt-in from live LLM calls. It exchanges a Login with Amazon (LWA)
  refresh token for a one-hour access token and sends it as
  `x-amz-access-token`. Credentials come only from the environment
  (`SP_API_LWA_CLIENT_ID`, `SP_API_LWA_CLIENT_SECRET`, `SP_API_REFRESH_TOKEN`)
  and are never stored on the transport, recorded or logged. It throttles to
  the documented rate limit.
* `RecordingHttpTransport` appends every exchange to a checksummed JSONL file
  (secret-scanned before writing).
* `ReplayHttpTransport` answers only from a recording, matched by request hash;
  an unrecorded request raises `HttpReplayMiss`. It never touches the network.
* `ScriptedHttpTransport` answers from a Python function (tests, fake mode).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from atlas_amazon import __version__
from atlas_amazon.jsonvalue import canonical_json, thaw
from atlas_amazon.semantic.records import ChecksummedJsonl, ensure_no_secrets

LIVE_MARKET_FLAG = "ATLAS_ALLOW_LIVE_MARKET"
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
CREDENTIAL_ENV = ("SP_API_LWA_CLIENT_ID", "SP_API_LWA_CLIENT_SECRET", "SP_API_REFRESH_TOKEN")
USER_AGENT = f"atlas-amazon/{__version__} (Language=Python)"
# Response headers kept in recordings (no secrets): request id and rate limit.
KEPT_HEADERS = ("x-amzn-requestid", "x-amzn-ratelimit-limit")


class HttpTransportError(Exception):
    pass


class LiveMarketDisabled(HttpTransportError):
    pass


class HttpReplayMiss(HttpTransportError):
    pass


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    base_url: str
    path: str
    params: tuple[tuple[str, str], ...] = ()

    @classmethod
    def get(cls, base_url: str, path: str, params: Mapping[str, str]) -> HttpRequest:
        return cls("GET", base_url, path, tuple(sorted((k, str(v)) for k, v in params.items())))

    @property
    def url(self) -> str:
        query = urllib.parse.urlencode(self.params)
        return f"{self.base_url}{self.path}" + (f"?{query}" if query else "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "base_url": self.base_url,
            "path": self.path,
            "params": [list(p) for p in self.params],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HttpRequest:
        return cls(
            data["method"],
            data["base_url"],
            data["path"],
            tuple((str(k), str(v)) for k, v in data["params"]),
        )


def http_request_hash(request: HttpRequest) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(request.to_dict()).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: Any  # parsed JSON, or None when the body was not JSON
    text: str | None = None  # raw body when it was not JSON
    headers: Mapping[str, str] = field(default_factory=dict)
    retrieved_at: str = ""  # ISO 8601 time of the original response
    transport: str = "unknown"
    synthetic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return thaw(asdict(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HttpResponse:
        return cls(**dict(data))


@runtime_checkable
class HttpTransport(Protocol):
    name: str
    is_live: bool

    def send(self, request: HttpRequest) -> HttpResponse: ...


class LiveSpApiTransport:
    """Live SP-API calls with LWA auth (stdlib HTTP). Disabled unless opted in."""

    name = "sp-api"
    is_live = True

    def __init__(
        self,
        *,
        allow_live: bool | None = None,
        rate_per_second: float = 5.0,
        timeout_s: float = 30.0,
        clock: Callable[[], datetime] | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._allow = allow_live
        self._interval = 1.0 / rate_per_second
        self._timeout = timeout_s
        self._clock = clock or (lambda: datetime.now(UTC))
        self._open = opener or urllib.request.urlopen
        self._token: tuple[str, float] | None = None  # (access token, expiry monotonic)
        self._last_call = 0.0

    def _check_allowed(self) -> None:
        allowed = (
            self._allow if self._allow is not None else os.environ.get(LIVE_MARKET_FLAG) == "1"
        )
        if not allowed:
            raise LiveMarketDisabled(
                f"live market-data calls are disabled; set {LIVE_MARKET_FLAG}=1 to enable them"
            )

    def _access_token(self) -> str:
        if self._token is not None and time.monotonic() < self._token[1]:
            return self._token[0]
        missing = [n for n in CREDENTIAL_ENV if not os.environ.get(n)]
        if missing:
            raise HttpTransportError(f"SP-API credentials missing: {missing}")
        body = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": os.environ["SP_API_REFRESH_TOKEN"],
                "client_id": os.environ["SP_API_LWA_CLIENT_ID"],
                "client_secret": os.environ["SP_API_LWA_CLIENT_SECRET"],
            }
        ).encode("utf-8")
        request = urllib.request.Request(LWA_TOKEN_URL, data=body, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with self._open(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:  # e.g. 400 invalid_grant, 401 invalid_client
            raise HttpTransportError(f"LWA token exchange failed: {_lwa_error(exc)}") from None
        try:
            data = json.loads(raw.decode("utf-8"))
            token = data["access_token"]
            lifetime = float(data.get("expires_in", 3600))
        except (ValueError, KeyError, TypeError, AttributeError):
            raise HttpTransportError("LWA token exchange failed: unexpected response") from None
        if not isinstance(token, str) or not token:
            raise HttpTransportError("LWA token exchange failed: empty access token")
        self._token = (token, time.monotonic() + max(60.0, lifetime - 60.0))
        return token

    def send(self, request: HttpRequest) -> HttpResponse:
        self._check_allowed()
        wait = self._interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        http = urllib.request.Request(request.url, method=request.method)
        http.add_header("x-amz-access-token", self._access_token())
        http.add_header("user-agent", USER_AGENT)
        http.add_header("accept", "application/json")
        self._last_call = time.monotonic()
        try:
            with self._open(http, timeout=self._timeout) as response:
                status, raw, headers = response.status, response.read(), response.headers
        except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a JSON error body
            status, raw, headers = exc.code, exc.read(), exc.headers
        text = raw.decode("utf-8", errors="replace")
        try:
            body, kept_text = json.loads(text), None
        except json.JSONDecodeError:
            body, kept_text = None, text[:2000]
        kept = {k: headers.get(k) for k in KEPT_HEADERS if headers and headers.get(k)}
        return HttpResponse(
            status=status,
            body=body,
            text=kept_text,
            headers=kept,
            retrieved_at=self._clock().isoformat(),
            transport=self.name,
        )


def _lwa_error(exc: urllib.error.HTTPError) -> str:
    """HTTP status plus LWA's `error` code (e.g. invalid_grant); never echoes the request."""
    try:
        code = json.loads(exc.read().decode("utf-8")).get("error")
    except (ValueError, AttributeError, OSError):
        code = None
    return f"HTTP {exc.code}" + (f" {code}" if isinstance(code, str) else "")


class ScriptedHttpTransport:
    """Deterministic responses for tests and fake mode. Never networked."""

    name = "scripted"

    def __init__(
        self, responder: Callable[[HttpRequest], HttpResponse], *, is_live: bool = True
    ) -> None:
        self._responder = responder
        self.is_live = is_live  # True lets tests exercise call caps
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        return self._responder(request)


class RecordingHttpTransport:
    """Pass-through that appends every exchange to a recording file."""

    def __init__(self, inner: HttpTransport, path: str | os.PathLike[str]) -> None:
        self.inner = inner
        self.name = inner.name
        self.is_live = inner.is_live
        self._file = ChecksummedJsonl(path)

    def send(self, request: HttpRequest) -> HttpResponse:
        response = self.inner.send(request)
        record = {
            "request_hash": http_request_hash(request),
            "request": request.to_dict(),
            "response": response.to_dict(),
        }
        ensure_no_secrets(record, "market recording")
        self._file.append([record])
        return response


class ReplayHttpTransport:
    """Serves recorded responses by exact request hash. Never calls the network."""

    name = "replay"
    is_live = False

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = path
        self._responses: dict[str, HttpResponse] = {}
        for record in ChecksummedJsonl(path).read():
            request = HttpRequest.from_dict(record["request"])
            if http_request_hash(request) != record["request_hash"]:
                raise HttpTransportError(f"{path}: recorded request does not match its hash")
            self._responses.setdefault(
                record["request_hash"], HttpResponse.from_dict(record["response"])
            )

    def __len__(self) -> int:
        return len(self._responses)

    def send(self, request: HttpRequest) -> HttpResponse:
        key = http_request_hash(request)
        try:
            return self._responses[key]
        except KeyError:
            raise HttpReplayMiss(f"no recorded response for request {key}") from None
