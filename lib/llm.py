"""Groq's free API, used through its OpenAI-compatible endpoint."""

from __future__ import annotations

import os

import streamlit as st

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
SMART = "openai/gpt-oss-120b"   # tool calling + strict JSON schema
FAST = "openai/gpt-oss-20b"
WHISPER = "whisper-large-v3-turbo"
TTS = "canopylabs/orpheus-v1-english"


def groq_key() -> str | None:
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:  # no secrets file
        key = None
    return key or os.getenv("GROQ_API_KEY")


def require_key() -> str:
    key = groq_key()
    if not key:
        st.error("This demo needs the GROQ_API_KEY secret, which isn't set on this deployment.")
        st.stop()
    return key


def friendly_error(exc: Exception) -> None:
    text = str(exc)
    if "rate_limit" in text or "429" in text:
        st.warning("The free AI quota is busy right now (lots of people trying demos). Please try again in a minute.")
    else:
        st.error(f"Something went wrong: {text[:300]}")


# --- Free-tier resilience ---------------------------------------------------------------
# Groq's free tier has per-model rate limits. Every project's OpenAI client goes through
# these patched methods: on a 429 for the big model, the same request is retried once on
# the smaller model (separate quota) instead of failing the demo.
FALLBACK = {SMART: FAST}


def _patch_openai() -> None:
    import openai
    from openai.resources.chat.completions import AsyncCompletions, Completions

    if getattr(Completions.create, "_zotriq_patched", False):
        return
    sync_create, async_create = Completions.create, AsyncCompletions.create

    def create(self, *args, **kwargs):
        try:
            return sync_create(self, *args, **kwargs)
        except openai.RateLimitError:
            if kwargs.get("model") not in FALLBACK:
                raise
            return sync_create(self, *args, **{**kwargs, "model": FALLBACK[kwargs["model"]]})

    async def acreate(self, *args, **kwargs):
        try:
            return await async_create(self, *args, **kwargs)
        except openai.RateLimitError:
            if kwargs.get("model") not in FALLBACK:
                raise
            return await async_create(self, *args, **{**kwargs, "model": FALLBACK[kwargs["model"]]})

    create._zotriq_patched = True
    Completions.create, AsyncCompletions.create = create, acreate


_patch_openai()
