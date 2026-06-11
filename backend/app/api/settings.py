from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.services.chat_model_settings import (
    CHAT_MODEL_SETTINGS_PATH,
    build_chat_model_settings,
    chat_model_settings_response,
    load_chat_model_settings,
    save_chat_model_settings,
)
from backend.app.services.openai_chat import OpenAIChatClient, OpenAIChatError


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/chat-model")
async def get_chat_model_settings() -> dict[str, Any]:
    return chat_model_settings_response(load_chat_model_settings(CHAT_MODEL_SETTINGS_PATH))


@router.put("/chat-model")
async def update_chat_model_settings(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        settings = save_chat_model_settings(payload, settings_path=CHAT_MODEL_SETTINGS_PATH)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return chat_model_settings_response(settings)


@router.post("/chat-model/test")
async def test_chat_model_settings(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        settings = build_chat_model_settings(payload, settings_path=CHAT_MODEL_SETTINGS_PATH)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    client = OpenAIChatClient(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model,
        timeout_seconds=settings.timeout_seconds,
    )
    try:
        preview = await client.chat(
            [{"role": "user", "content": "Reply with OK only."}],
            temperature=0,
        )
    except OpenAIChatError as exc:
        return {
            "ok": False,
            "provider": settings.provider,
            "model": settings.model,
            "base_url": settings.base_url,
            "message": str(exc)[:500],
        }

    return {
        "ok": True,
        "provider": settings.provider,
        "model": settings.model,
        "base_url": settings.base_url,
        "message": "Connection test succeeded.",
        "preview": str(preview or "")[:120],
    }
