"""Shared strict request validation, private headers and API error mapping."""

from fastapi import HTTPException, Response
from pydantic import BaseModel, ConfigDict


def private_response(response: Response):
    """Prevent owner-facing API responses from being stored in shared caches."""
    response.headers["Cache-Control"] = "no-store"


def invoke(callback, *args, **kwargs):
    """Translate domain lookup, conflict and validation errors into HTTP responses."""
    try:
        return callback(*args, **kwargs)
    except LookupError as error:
        raise HTTPException(404, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from None
    except ValueError as error:
        raise HTTPException(400, str(error)) from None


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
