#!/usr/bin/env python3
"""HTTP adapters for the BIL system.

Wraps outbound calls to LLM providers and n8n webhooks with httpx, per the
adapter layer sketched in plan.md (bil/adapters/openai.py, claude.py, n8n.py).
Kept as plain functions rather than a client class since each call is
independent and stateless.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


def _require_key(api_key: Optional[str], env_var: str) -> str:
    key = api_key or os.environ.get(env_var)
    if not key:
        raise RuntimeError(f"{env_var} not set and no api_key provided")
    return key


def call_openai(
    bil_tokens: str,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    base_url: str = "https://api.openai.com/v1",
) -> Dict[str, Any]:
    """Send a BIL token stream to OpenAI's Chat Completions API."""
    key = _require_key(api_key, "OPENAI_API_KEY")
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": f"BIL:{bil_tokens}"}],
            },
        )
        response.raise_for_status()
        return response.json()


def call_claude(
    bil_tokens: str,
    model: str = "claude-sonnet-5",
    api_key: Optional[str] = None,
    base_url: str = "https://api.anthropic.com/v1",
    anthropic_version: str = "2023-06-01",
) -> Dict[str, Any]:
    """Send a BIL token stream to Anthropic's Messages API."""
    key = _require_key(api_key, "ANTHROPIC_API_KEY")
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.post(
            f"{base_url}/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": anthropic_version,
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": f"BIL:{bil_tokens}"}],
            },
        )
        response.raise_for_status()
        return response.json()


def forward_to_n8n(webhook_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST a BIL round-trip payload to an external n8n webhook."""
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.post(webhook_url, json=payload)
        response.raise_for_status()
        return response.json()
