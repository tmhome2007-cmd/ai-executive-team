"""Owner-requested local conversation audio API routes."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Response
from pydantic import Field
from api.common import StrictRequest, invoke, private_response

router = APIRouter(dependencies=[Depends(private_response)])


class ConversationSpeech(StrictRequest):
    source_kind: Literal["contribution", "discussion"]
    source_id: int = Field(strict=True, ge=1, le=9223372036854775807)
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")


@router.post("/conversation-audio")
def generate_conversation_audio(request: ConversationSpeech):
    from workflows.conversation_audio import generate

    return invoke(generate, request.source_kind, request.source_id, request.request_id)


@router.delete("/conversation-audio/requests/{request_id}")
def cancel_conversation_audio(
    request_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$")],
):
    from workflows.conversation_audio import cancel

    return invoke(cancel, request_id)


@router.get("/conversation-audio/{key}")
def get_conversation_audio(key: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")]):
    from workflows.conversation_audio import audio_bytes

    return Response(
        content=invoke(audio_bytes, key),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/conversation-audio/{key}")
def delete_conversation_audio(key: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")]):
    from workflows.conversation_audio import delete_audio

    return invoke(delete_audio, key)
