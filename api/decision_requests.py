"""Authenticated generation status and explicit recovery closure, no retries."""

from fastapi import APIRouter, Depends, HTTPException
from memory import decision_requests


def make_request_router(verify_api_key):
    router = APIRouter(dependencies=[Depends(verify_api_key)])

    @router.get("/decisions/requests/{request_id}")
    def inspect(request_id: str):
        try:
            value = decision_requests.inspect(request_id)
        except ValueError:
            raise HTTPException(400, "Invalid request identity.") from None
        if value is None:
            raise HTTPException(
                404, "No tracked request found; its delivery may still be pending."
            )
        return value

    @router.post("/decisions/requests/{request_id}/close")
    def close(request_id: str):
        try:
            return decision_requests.close(request_id)
        except decision_requests.RequestConflict:
            raise HTTPException(
                409, "The meeting is still queued or running. Check status again later."
            ) from None
        except ValueError:
            raise HTTPException(400, "Invalid request identity.") from None

    return router
