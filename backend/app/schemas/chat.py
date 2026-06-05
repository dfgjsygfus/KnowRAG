from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatStreamRequest(BaseModel):
    """Single-turn question submitted by the desktop pet."""

    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized
