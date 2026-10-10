"""Owner-authenticated read-only company knowledge navigation."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query
from api.common import invoke, private_response
from memory.company_knowledge import search_knowledge, knowledge_record

router = APIRouter(dependencies=[Depends(private_response)])
Kind = Literal[
    "goal",
    "decision",
    "action",
    "outcome",
    "lesson",
    "skill",
    "evidence",
    "brief",
    "sample",
    "review",
]


@router.get("/company/knowledge")
def knowledge_search(
    query: str = Query("", max_length=200),
    kind: str = Query("all", max_length=20),
    mode: Literal["history", "current"] = "history",
    limit: int = Query(30, ge=1, le=50),
    offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(search_knowledge, query, kind, mode, limit, offset)


@router.get("/company/knowledge/{kind}/{ident}")
def knowledge_detail(
    kind: Kind,
    ident: Annotated[int, Path(ge=1, le=9223372036854775807)],
    link_offset: int = Query(0, ge=0, le=9223372036854775807),
):
    return invoke(knowledge_record, kind, ident, link_offset)
