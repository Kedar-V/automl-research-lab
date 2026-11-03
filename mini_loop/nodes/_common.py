"""Shared helpers for isolated simple-loop node scripts."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMORY_PATH = ROOT / "memory" / "research_memory.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    # Xing4.0 currently answers when the shared free-daily pool is exhausted.
    "xingchen-agi/xing4.0-29b-a4b:free",
)


def read_json_stdin() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, default=str))
    sys.stdout.flush()


def llm_configured() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def openrouter_chat(
    system: str,
    user: str,
    *,
    max_tokens: int = 1200,
    temperature: float = 0.2,
    retries: int = 2,
) -> tuple[str | None, str | None]:
    """Live OpenRouter chat. Prefer JSON in content; disable reasoning when allowed."""
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None, "OPENROUTER_API_KEY not set"
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Reasoning models otherwise burn the budget before emitting JSON.
        "reasoning": {"enabled": False},
    }
    last_err: str | None = None
    for attempt in range(max(1, retries)):
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost/automl-research-lab",
                "X-Title": "Simple Research Loop",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_err = f"HTTP {exc.code}: {detail}"
            # Some free endpoints require reasoning — drop the disable and retry.
            if (
                exc.code == 400
                and "reasoning is mandatory" in detail.lower()
                and "reasoning" in body
            ):
                body.pop("reasoning", None)
            continue
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            continue

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            last_err = f"unexpected response: {str(data)[:300]}"
            continue

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            # Last-resort: some providers park text in reasoning.
            reasoning = message.get("reasoning")
            if isinstance(reasoning, str) and reasoning.strip():
                content = reasoning
            else:
                last_err = "empty model content"
                # Give the model more room on retry.
                body["max_tokens"] = min(int(body["max_tokens"]) + 400, 2400)
                continue
        return content.strip(), None

    return None, last_err or "openrouter failed"


def extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def load_memory() -> dict[str, Any]:
    if not MEMORY_PATH.exists():
        return {"history": [], "findings": [], "lessons": []}
    try:
        return json.loads(MEMORY_PATH.read_text())
    except json.JSONDecodeError:
        return {"history": [], "findings": [], "lessons": []}


def save_memory(mem: dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(mem, indent=2, default=str))
