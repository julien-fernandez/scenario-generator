"""Backends LLM — une fonction `complete(system, prompt, ...) -> str`.

Deux backends, sans SDK :
- `anthropic`  : API Messages, clé `ANTHROPIC_API_KEY`.
- `claude-cli` : `claude -p`, avec l'authentification de Claude Code déjà en place.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from typing import Callable, Protocol

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class Complete(Protocol):
    def __call__(self, system: str, prompt: str, *, max_tokens: int,
                 temperature: float) -> str: ...


def anthropic_backend(model: str) -> Complete:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY manquant")

    def complete(system: str, prompt: str, *, max_tokens: int,
                 temperature: float) -> str:
        payload = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            body = json.loads(r.read())
        return "".join(b.get("text", "") for b in body.get("content", []))

    return complete


def claude_cli_backend(model: str) -> Complete:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("commande `claude` introuvable")

    def complete(system: str, prompt: str, *, max_tokens: int,
                 temperature: float) -> str:
        # La CLI ne règle ni max_tokens ni temperature : on les ignore.
        proc = subprocess.run(
            [exe, "-p", "--model", model, "--system-prompt", system,
             "--tools", "", "--output-format", "json",
             "--no-session-persistence"],
            input=prompt, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"claude -p a échoué : {proc.stderr.strip()[:500]}")
        out = json.loads(proc.stdout)
        if out.get("is_error"):
            raise RuntimeError(f"claude -p : {out.get('result', '')[:500]}")
        return out.get("result", "")

    return complete


BACKENDS: dict[str, Callable[[str], Complete]] = {
    "anthropic": anthropic_backend,
    "claude-cli": claude_cli_backend,
}


def get_backend(name: str, model: str | None = None) -> Complete:
    """`auto` : l'API si une clé est posée, sinon la CLI `claude`."""
    if name == "auto":
        name = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "claude-cli"
    if name not in BACKENDS:
        raise ValueError(f"backend inconnu : {name} (choix : auto, {', '.join(BACKENDS)})")
    return BACKENDS[name](model or os.environ.get("SCENARIO_MODEL", DEFAULT_MODEL))
