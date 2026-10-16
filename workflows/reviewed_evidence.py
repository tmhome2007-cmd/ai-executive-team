"""Experimental explicit supersession of source excerpts; no automatic fact extraction."""

from pydantic import BaseModel, ConfigDict, Field


class EvidenceUpdate(BaseModel):
    """A caller-reviewed relationship, never a model-inferred replacement."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    field: str = Field(min_length=1, max_length=100)
    old_source: str = Field(min_length=1, max_length=80)
    old_quote: str = Field(min_length=8, max_length=600)
    current_source: str = Field(min_length=1, max_length=80)
    current_quote: str = Field(min_length=8, max_length=600)


def project_current_evidence(sources, updates):
    """Exclude only explicitly superseded spans, preserving originals and other text.

    Does not decide truth, parse corrections or establish freshness/consent. The
    caller must have reviewed which exact subject/field the update concerns.
    Ambiguous, overlapping or chained edits fail instead of guessing precedence.
    """
    if not sources or any(
        not isinstance(key, str)
        or not key.strip()
        or not isinstance(value, str)
        or not value.strip()
        for key, value in sources.items()
    ):
        raise ValueError("Nonempty identified sources are required")
    if len(updates) > 16:
        raise ValueError("Too many reviewed updates")
    fields, retired_sources, current_sources = set(), set(), set()
    spans = {}
    for update in updates:
        if not isinstance(update, EvidenceUpdate):
            raise ValueError("Updates must be typed and explicitly reviewed")
        if (
            not update.field.strip()
            or update.field in fields
            or update.old_source == update.current_source
            or update.old_source not in sources
            or update.current_source not in sources
            or not update.old_quote.strip()
            or not update.current_quote.strip()
            or sources[update.old_source].count(update.old_quote) != 1
            or update.current_quote not in sources[update.current_source]
        ):
            raise ValueError("Missing, ambiguous or conflicting reviewed evidence")
        fields.add(update.field)
        retired_sources.add(update.old_source)
        current_sources.add(update.current_source)
        start = sources[update.old_source].index(update.old_quote)
        span = (start, start + len(update.old_quote))
        existing = spans.setdefault(update.old_source, [])
        if any(span[0] < end and begin < span[1] for begin, end in existing):
            raise ValueError("Overlapping superseded excerpts")
        existing.append(span)
    if retired_sources & current_sources:
        raise ValueError("Chained updates require a separate resolved snapshot")
    projected = dict(sources)
    for key, ranges in spans.items():
        del projected[key]
        cursor = 0
        for number, (start, end) in enumerate(
            [*sorted(ranges), (len(sources[key]), len(sources[key]))], 1
        ):
            fragment = sources[key][cursor:start]
            if fragment.strip():
                fragment_id = f"{key}:part{number}"
                if len(fragment_id) > 80 or fragment_id in sources:
                    raise ValueError("Ambiguous projected source identity")
                projected[fragment_id] = fragment
            cursor = end
    current = [
        {
            "field": update.field,
            "source_id": update.current_source,
            "quote": update.current_quote,
        }
        for update in updates
    ]
    return projected, current
