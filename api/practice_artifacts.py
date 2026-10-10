"""Owner-authenticated inert exports and bounded comparisons of saved samples."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import Field
from api.common import StrictRequest, invoke, private_response
from memory.practice_artifacts import (
    export_sample,
    list_artifacts,
    download_artifact,
    compare_artifacts,
)

router = APIRouter(dependencies=[Depends(private_response)])
Identity = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]


class ArtifactExport(StrictRequest):
    sample_id: Identity
    kind: Literal["txt", "md"]


@router.post("/practice-artifacts")
def artifact_export(request: ArtifactExport):
    return invoke(export_sample, request.sample_id, request.kind)


@router.get("/practice-artifacts")
def artifact_list(
    brief_id: int = Query(ge=1, le=9223372036854775807),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(list_artifacts, brief_id, limit, offset)


@router.get("/practice-artifacts/compare")
def artifact_compare(
    before_id: int = Query(ge=1, le=9223372036854775807),
    after_id: int = Query(ge=1, le=9223372036854775807),
):
    return invoke(compare_artifacts, before_id, after_id)


@router.get("/practice-artifacts/{ident}/download")
def artifact_download(ident: Annotated[int, Path(ge=1, le=9223372036854775807)]):
    data, filename = invoke(download_artifact, ident)
    return Response(
        data,
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
