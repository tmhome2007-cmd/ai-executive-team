"""Owner-only metadata inspection and cooperative private generation controls."""

from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query
from pydantic import Field
from api.common import StrictRequest, invoke, private_response
from memory.run_inspector import list_runs, get_run, stop_run
from workflows.business_discovery import continue_private_run

router = APIRouter(dependencies=[Depends(private_response)])
Identity = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]


class RunControl(StrictRequest):
    expected_version: Identity


class RunContinuation(RunControl):
    expected_brief_version: Identity


@router.get("/runs")
def runs_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(list_runs, limit, offset)


@router.get("/runs/{ident}")
def run_get(ident: Annotated[int, Path(ge=1, le=9223372036854775807)]):
    return invoke(get_run, ident)


@router.post("/runs/{ident}/stop")
def run_stop(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: RunControl
):
    return invoke(stop_run, ident, request.expected_version)


@router.post("/runs/{ident}/continue")
def run_continue(
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)], request: RunContinuation
):
    return invoke(
        continue_private_run,
        ident,
        request.expected_version,
        request.expected_brief_version,
        wait_seconds=0,
    )
