"""Revision formatting and bounded checks; owner assessment remains separate."""

import json
import re
from pydantic import BaseModel, ConfigDict, Field
from memory.experiments import _text


class PracticeRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Enforce text bounds after generation. Large JSON-schema string bounds can
    # make local constrained decoding prohibitively slow.
    revised_sample: str = Field(
        description="The complete revised deliverable, including requested instructions and FAQ answers. Never only a title. Use generic functions when interface controls are unspecified."
    )
    changes: list[str] = Field(min_length=1, max_length=10)
    remaining_unknowns: list[str] = Field(min_length=1, max_length=10)


def render_revision(raw, exercise, previous_sample=None):
    if isinstance(raw, str):
        wrapper = re.fullmatch(r"\s*```(?:json)?\s*\n(.*)\n```\s*", raw, re.S | re.I)
        if wrapper:
            raw = wrapper.group(1)
    try:
        result = PracticeRevision.model_validate_json(raw)
    except (ValueError, TypeError):
        raise ValueError(
            "Return a JSON object with revised_sample as one text string (not a nested object), changes as a list of strings, and remaining_unknowns as a list of strings"
        ) from None
    sample = validate_sample(result.revised_sample, exercise)
    # Validate model metadata, but never publish its unsupported change claims.
    [_text(c, "change description", 700) for c in result.changes]
    comparison = "Previous sample unavailable; no change comparison is established."
    if previous_sample is not None:
        from difflib import SequenceMatcher

        before = clean_deliverable(previous_sample, exercise=exercise).splitlines()
        after = sample.splitlines()
        removed = added = 0
        for tag, i, j, k, l in SequenceMatcher(
            None, before, after, autojunk=False
        ).get_opcodes():
            if tag in {"replace", "delete"}:
                removed += sum(bool(line.strip()) for line in before[i:j])
            if tag in {"replace", "insert"}:
                added += sum(bool(line.strip()) for line in after[k:l])
        comparison = f"Literal text comparison with the parent sample: {removed} non-empty lines removed or replaced; {added} non-empty lines added or replaced. These counts do not establish correctness or improvement. Compare the saved samples and record a fresh review."
    unknowns = [_text(c, "remaining unknown", 700) for c in result.remaining_unknowns]
    return (
        "**Revised practice sample — awaiting owner assessment**\n\n"
        + sample
        + "\n\n**Text comparison — recorded samples, not AI change claims**\n"
        + comparison
        + "\n\n**Remaining unknowns**\n"
        + "\n".join("- " + c for c in unknowns)
        + "\n\nNo passing result, learned competence or launch approval is recorded by this revision."
    )


def clean_deliverable(body, preserve_unknowns=True, exercise=""):
    """Drop report scaffolding, keeping actual deliverable sections in order."""
    metadata = {
        "findings",
        "unknowns",
        "next action",
        "changes",
        "remaining unknowns",
        "model-suggested checks",
        "minimum review controls",
        "changes described by ai — verify against the previous sample",
        "text comparison — recorded samples, not ai change claims",
    }
    metadata = {
        heading
        for heading in metadata
        if not re.search(r"\b" + re.escape(heading) + r"\b", exercise, re.I)
    }
    lines = []
    unknowns = []
    section = None
    skip = False
    for line in body.splitlines():
        heading = line.strip().strip("#").strip().strip("*").strip().rstrip(":").lower()
        if heading in metadata:
            section = heading
            skip = True
            continue
        if line.strip().startswith(("**", "#")) and heading not in metadata:
            skip = False
            section = None
        if (
            skip
            and section in {"unknowns", "remaining unknowns"}
            and line.strip().startswith(("- ", "* "))
        ):
            item = line.strip()[2:].strip()
            if item and item not in unknowns:
                unknowns.append(item)
        if not skip:
            lines.append(line)
    body = "\n".join(lines).strip()
    if preserve_unknowns and unknowns:
        body += "\n\n**Remaining unknowns**\n" + "\n".join(
            "- " + item for item in unknowns
        )
    return body


def validate_sample(raw, exercise, preserve_unknowns=False):
    sample = _text(raw, "revised sample", 20000)
    if "guide" in exercise.lower() and "\n" not in sample and "\\n" in sample:
        sample = sample.replace("\\n", "\n")
    sample = clean_deliverable(
        sample, preserve_unknowns=preserve_unknowns, exercise=exercise
    )
    if not sample or ("guide" in exercise.lower() and len(sample) < 80):
        raise ValueError(
            "Revision must contain the deliverable, not just a title or change list"
        )
    if "guide" in exercise.lower() and "task" in exercise.lower():
        if any(stem not in sample.lower() for stem in ("creat", "edit", "complet")):
            raise ValueError(
                "Revised task guide must explain creating, editing and completing tasks"
            )
        if len(re.findall(r"(?m)^\s*\d+[.)]\s+\S", sample)) < 3:
            raise ValueError(
                "Revised task guide requires numbered instructions, not a title"
            )
    if "faq" in exercise.lower() and re.search(r"\b(?:three|3)\b", exercise, re.I):
        if len(re.findall(r"(?im)^\s*(?:\*\*)?A\s*[:.]", sample)) < 3:
            raise ValueError(
                "Provide three complete FAQ answers, each on a line starting A:"
            )
    # Regression for the observed UI fabrication: no positive instructions for
    # unprovided controls/fields. This is not a universal truth verifier.
    details = [
        "pencil icon",
        "checkbox",
        "due date",
        "due time",
        "completed section",
        "save button",
        "plus icon",
        '"+"',
        "'+'",
        "tasks tab",
        'click "save"',
        "task name and description",
        "task completion date",
        "removed from the task list",
    ]
    for detail in details:
        if detail not in exercise.lower():
            for line in sample.splitlines():
                uncertainty = re.search(
                    r"\b(?:unknown|unspecified|not provided|not specified|no evidence)\b",
                    line,
                    re.I,
                ) and not re.search(
                    r"\b(?:click|tap|press|select|enter|set|use|open|add)\b", line, re.I
                )
                prohibited = re.search(
                    r"\b(?:do not|cannot)\s+(?:click|tap|press|select|enter|set|use|open|add)\b",
                    line,
                    re.I,
                )
                removed = re.search(
                    r"^\s*(?:[-*]\s*)?(?:removed|deleted|omitted)\b", line, re.I
                )
                if detail in line.lower() and not (
                    uncertainty or prohibited or removed
                ):
                    raise ValueError(
                        "Revision still invents an interface detail absent from the exercise: "
                        + detail
                    )
    if re.search(
        r"\b(?:meets all|passes all|all checks (?:pass|passed)|owner (?:approved|accepted))\b",
        sample,
        re.I,
    ):
        raise ValueError(
            "AI revision cannot establish passing checks or owner approval"
        )
    if re.search(
        r"reminders?\s+(?:(?:functionality|behavior|support|feature)\s+)?(?:is\s+|are\s+)?(?:unknown|unspecified)",
        exercise,
        re.I,
    ):
        for line in sample.splitlines():
            action = re.search(
                r"\b(?:set|enable|configure|add)\b[^\n.]{0,80}\breminders?\b",
                line,
                re.I,
            )
            negative = re.search(
                r"\b(?:do not|cannot|can.not)\s+(?:set|enable|configure|add)\b",
                line,
                re.I,
            )
            question = re.match(r"\s*(?:\*\*)?Q\s*:", line, re.I)
            observation = re.search(
                r"\b(?:ability|whether|unknown|unspecified)\b", line, re.I
            ) and not re.match(
                r"\s*(?:\d+[.)]\s+|[-*]\s+|A:\s*)?(?:set|enable|configure|add|you)\b",
                line,
                re.I,
            )
            if action and not (negative or question or observation):
                raise ValueError(
                    "Unknown reminder functionality cannot be an instruction to set a reminder"
                )
    if re.search(
        r"reminders?\s+(?:(?:functionality|behavior|support|feature)\s+)?(?:is\s+|are\s+)?(?:unknown|unspecified)",
        exercise,
        re.I,
    ) and not re.search(r"reminder.*unknown", sample, re.I):
        sample += "\n\nReminder functionality is unknown, as specified in the exercise."
    return sample
