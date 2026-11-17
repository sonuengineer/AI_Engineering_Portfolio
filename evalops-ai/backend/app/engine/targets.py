"""Target executors: turn a test case into a normalized TargetOutput, recording spans.

- llm: render the prompt version and call the model config's provider.
- http_nexus / http_datawise: call those apps' public HTTP contracts (MASTER_ARCHITECTURE.md
  section 3). Credentials are resolved from environment variables named in target.config
  (`email_env`, `password_env`); they are never stored in the database.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Protocol

import httpx

from app.core.config import get_settings
from app.evaluators.base import CaseData, TargetOutput
from app.llm import get_provider
from app.llm.base import GenerationRequest, ProviderError, TransientProviderError
from app.services.tracing import TraceRecorder

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


class TargetExecutor(Protocol):
    def execute(self, case: CaseData, tracer: TraceRecorder, timeout_s: float) -> TargetOutput: ...

    def close(self) -> None: ...


def render_template(template: str, case: CaseData) -> str:
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key == "input":
            return case.input
        if key == "contexts":
            return "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(case.reference_contexts))
        if key.startswith("metadata."):
            return str(case.metadata.get(key.split(".", 1)[1], ""))
        return m.group(0)

    return _VAR_RE.sub(sub, template)


def case_payload(case: CaseData) -> dict[str, Any]:
    return {
        "external_id": case.external_id,
        "input": case.input,
        "reference_contexts": case.reference_contexts,
        "metadata": case.metadata,
    }


class LLMTargetExecutor:
    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.model_cfg: dict[str, Any] = snapshot["model_config"]
        self.prompt: dict[str, Any] = snapshot.get("prompt_version") or {
            "system_prompt": "", "user_template": "{{input}}", "content_hash": None, "version": None,
        }
        self.provider = get_provider(self.model_cfg["provider"])

    def execute(self, case: CaseData, tracer: TraceRecorder, timeout_s: float) -> TargetOutput:
        with tracer.span("render_prompt", "prompt", prompt_hash=self.prompt.get("content_hash"),
                         prompt_version=self.prompt.get("version")) as sp:
            user_prompt = render_template(self.prompt["user_template"], case)
            sp.set(prompt_chars=len(user_prompt), prompt_preview=user_prompt[:500])
        req = GenerationRequest(
            system_prompt=self.prompt.get("system_prompt") or "",
            user_prompt=user_prompt,
            params=dict(self.model_cfg.get("params") or {}),
            timeout_s=timeout_s,
            case=case_payload(case) if not self.provider.is_real_llm else None,
        )
        with tracer.span("model_call", "model_call", provider=self.provider.name,
                         model=self.model_cfg["model"]) as sp:
            res = self.provider.generate(req, self.model_cfg["model"])
            sp.set(input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                   tokens_estimated=res.tokens_estimated, output_preview=res.text[:500], notes=res.notes)
        cost = (res.input_tokens / 1000.0) * float(self.model_cfg.get("price_in_per_1k") or 0) + (
            res.output_tokens / 1000.0
        ) * float(self.model_cfg.get("price_out_per_1k") or 0)
        parsed = res.parsed if isinstance(res.parsed, dict) else None
        out = TargetOutput(
            text=res.text, json=res.parsed, input_tokens=res.input_tokens, output_tokens=res.output_tokens,
            tokens_estimated=res.tokens_estimated, cost_usd=cost, provider=res.provider, model=res.model,
        )
        if "{{contexts}}" in self.prompt["user_template"].replace(" ", ""):
            out.contexts = list(case.reference_contexts)  # these texts were given to the model in the prompt
        # Scripted outputs may mimic structured targets (citations/contexts/status/rows).
        if parsed:
            out.text = str(parsed.get("answer") or parsed.get("insight") or parsed.get("text") or res.text)
            out.citations = [str(c.get("document_id", c)) if isinstance(c, dict) else str(c)
                             for c in parsed.get("citations", [])]
            if "contexts" in parsed:
                out.contexts = [str(c) for c in parsed.get("contexts", [])]
            out.status = parsed.get("status")
            out.rows = parsed.get("rows")
            out.columns = parsed.get("columns", [])
            out.sql = parsed.get("sql")
        return out

    def close(self) -> None:
        return None


def _env(name: str | None) -> str | None:
    if not name:
        return None
    val = os.environ.get(name)
    if val:
        return val
    return getattr(get_settings(), name.lower(), None)


class _HttpTargetBase:
    login_path = "/api/v1/auth/login"
    ask_path = ""
    default_base_env = ""
    default_email_env = ""
    default_password_env = ""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        cfg: dict[str, Any] = snapshot["target"].get("config") or {}
        self.base_url = (cfg.get("base_url") or _env(cfg.get("base_url_env") or self.default_base_env) or "").rstrip("/")
        if not self.base_url:
            raise ProviderError("target base URL is not configured")
        self._email = _env(cfg.get("email_env") or self.default_email_env)
        self._password = _env(cfg.get("password_env") or self.default_password_env)
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)
        self._token: str | None = None
        self._lock = threading.Lock()
        # NEXUS document ids are per-seed UUIDs; titles are stable, so benchmarks match on titles by default.
        self.citation_key = str(cfg.get("citation_key") or "document_title")

    def _login(self, tracer: TraceRecorder, force: bool = False) -> str:
        with self._lock:
            if self._token and not force:
                return self._token
            if not self._email or not self._password:
                raise ProviderError("target credentials are not configured (set the *_EMAIL/*_PASSWORD env vars)")
            with tracer.span("auth_login", "http", method="POST", url=self.base_url + self.login_path) as sp:
                r = self._post(self.login_path, {"email": self._email, "password": self._password}, None, 15.0)
                sp.set(status_code=r.status_code)
            if r.status_code != 200:
                raise ProviderError(f"login failed with HTTP {r.status_code}")
            self._token = str(r.json()["access_token"])
            return self._token

    def _post(self, path: str, body: dict[str, Any], token: str | None, timeout_s: float) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            return self._client.post(path, json=body, headers=headers, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise TransientProviderError(f"timeout calling {path}") from exc
        except httpx.TransportError as exc:
            raise TransientProviderError(f"connection error calling {path}: {type(exc).__name__}") from exc

    def _ask(self, body: dict[str, Any], tracer: TraceRecorder, timeout_s: float) -> dict[str, Any]:
        token = self._login(tracer)
        for attempt in range(2):
            with tracer.span("ask", "http", method="POST", url=self.base_url + self.ask_path,
                             request_body=body) as sp:
                r = self._post(self.ask_path, body, token, timeout_s)
                sp.set(status_code=r.status_code, response_bytes=len(r.content))
            if r.status_code == 401 and attempt == 0:
                token = self._login(tracer, force=True)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                raise TransientProviderError(f"HTTP {r.status_code} from {self.ask_path}")
            if r.status_code != 200:
                raise ProviderError(f"HTTP {r.status_code} from {self.ask_path}: {r.text[:200]}")
            data: dict[str, Any] = r.json()
            return data
        raise ProviderError("unauthorized after re-login")

    def close(self) -> None:
        self._client.close()


class NexusTargetExecutor(_HttpTargetBase):
    ask_path = "/api/v1/chat/ask"
    default_base_env = "NEXUS_BASE_URL"
    default_email_env = "NEXUS_EMAIL"
    default_password_env = "NEXUS_PASSWORD"

    def execute(self, case: CaseData, tracer: TraceRecorder, timeout_s: float) -> TargetOutput:
        data = self._ask({"question": case.input, "conversation_id": None}, tracer, timeout_s)
        usage = data.get("usage") or {}
        citations = data.get("citations") or []
        with tracer.span("retrieval_reported", "retrieval", source="reported by target response",
                         citation_count=len(citations), context_count=len(data.get("contexts") or []),
                         target_latency_ms=data.get("latency_ms")):
            pass
        return TargetOutput(
            text=str(data.get("answer") or ""),
            json={k: data.get(k) for k in ("conversation_id", "provider", "model", "latency_ms", "usage")},
            citations=[str(c.get(self.citation_key) or c.get("document_id")) for c in citations if isinstance(c, dict)],
            contexts=[c if isinstance(c, str) else str((c or {}).get("text", "")) for c in data.get("contexts") or []],
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            cost_usd=float(usage.get("estimated_cost_usd") or 0.0),
            provider=data.get("provider"),
            model=data.get("model"),
        )


class DatawiseTargetExecutor(_HttpTargetBase):
    ask_path = "/api/v1/questions/ask"
    default_base_env = "DATAWISE_BASE_URL"
    default_email_env = "DATAWISE_EMAIL"
    default_password_env = "DATAWISE_PASSWORD"

    def execute(self, case: CaseData, tracer: TraceRecorder, timeout_s: float) -> TargetOutput:
        data = self._ask({"question": case.input}, tracer, timeout_s)
        clar = data.get("clarification") or {}
        text = data.get("insight") or clar.get("question") or data.get("rejection_reason") or ""
        return TargetOutput(
            text=str(text),
            json={k: data.get(k) for k in ("status", "plan", "validation", "row_count", "provider", "latency_ms",
                                           "clarification", "rejection_reason")},
            status=data.get("status"),
            sql=data.get("sql"),
            columns=[str(c) for c in data.get("columns") or []],
            rows=data.get("rows"),
            provider=data.get("provider"),
        )


def build_executor(snapshot: dict[str, Any]) -> TargetExecutor:
    kind = snapshot["target"]["kind"]
    if kind == "llm":
        return LLMTargetExecutor(snapshot)
    if kind == "http_nexus":
        return NexusTargetExecutor(snapshot)
    if kind == "http_datawise":
        return DatawiseTargetExecutor(snapshot)
    raise ProviderError(f"unknown target kind '{kind}'")


def backoff_seconds(attempt: int, base: float = 0.25, cap: float = 8.0) -> float:
    """Exponential backoff without jitter (jitter comes from the seeded RNG in the runner)."""
    return min(cap, base * (2 ** attempt))


def monotonic_ms() -> float:
    return time.perf_counter() * 1000.0
