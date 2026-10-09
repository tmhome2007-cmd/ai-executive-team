"""Revision formatting and bounded checks; owner assessment remains separate."""
import json
import re
from pydantic import BaseModel, ConfigDict, Field
from memory.experiments import _text


class PracticeRevision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Enforce text bounds after generation. Large JSON-schema string bounds can
    # make local constrained decoding prohibitively slow.
    revised_sample: str = Field(description='The complete revised deliverable, including requested instructions and FAQ answers. Never only a title. Use generic functions when interface controls are unspecified.')
    changes: list[str] = Field(min_length=1, max_length=10)
    remaining_unknowns: list[str] = Field(min_length=1, max_length=10)


def render_revision(raw, exercise):
    if isinstance(raw, str):
        wrapper = re.fullmatch(r'\s*```(?:json)?\s*\n(.*)\n```\s*', raw, re.S | re.I)
        if wrapper:
            raw = wrapper.group(1)
    try:
        result = PracticeRevision.model_validate_json(raw)
    except (ValueError, TypeError):
        raise ValueError('Return a JSON object with revised_sample as one text string (not a nested object), changes as a list of strings, and remaining_unknowns as a list of strings') from None
    sample = _text(result.revised_sample, 'revised sample', 20000)
    if 'guide' in exercise.lower() and '\n' not in sample and '\\n' in sample:
        sample = sample.replace('\\n', '\n')
    if len(sample) < 80:
        raise ValueError('Revision must contain the deliverable, not just a title or change list')
    if 'guide' in exercise.lower() and 'task' in exercise.lower():
        if any(stem not in sample.lower() for stem in ('creat', 'edit', 'complet')):
            raise ValueError('Revised task guide must explain creating, editing and completing tasks')
        if len(re.findall(r'(?m)^\s*\d+[.)]\s+\S', sample)) < 3:
            raise ValueError('Revised task guide requires numbered instructions, not a title')
    if 'faq' in exercise.lower() and re.search(r'\b(?:three|3)\b', exercise, re.I):
        if len(re.findall(r'(?im)^\s*(?:\*\*)?A\s*[:.]', sample)) < 3:
            raise ValueError('Provide three complete FAQ answers, each on a line starting A:')
    # Regression for the observed UI fabrication: no positive instructions for
    # unprovided controls/fields. This is not a universal truth verifier.
    details = ['pencil icon', 'checkbox', 'due date', 'due time', 'completed section', 'save button', 'plus icon', '"+"',
               'task name and description', 'task completion date', 'removed from the task list']
    for detail in details:
        if detail not in exercise.lower():
            for line in sample.splitlines():
                if detail in line.lower() and not re.search(r'\b(?:unknown|unspecified|not provided|not specified|cannot|do not|no evidence)\b', line, re.I) and not re.search(r'^\s*(?:[-*]\s*)?(?:removed|deleted|omitted)\b', line, re.I):
                    raise ValueError('Revision still invents an interface detail absent from the exercise: ' + detail)
    if re.search(r'\b(?:meets all|passes all|all checks (?:pass|passed)|owner (?:approved|accepted))\b', sample, re.I):
        raise ValueError('AI revision cannot establish passing checks or owner approval')
    changes = [_text(c, 'change description', 700) for c in result.changes]
    unknowns = [_text(c, 'remaining unknown', 700) for c in result.remaining_unknowns]
    return ('**Revised practice sample — awaiting owner assessment**\n\n' + sample
            + '\n\n**Changes described by AI — verify against the previous sample**\n' + '\n'.join('- ' + c for c in changes)
            + '\n\n**Remaining unknowns**\n' + '\n'.join('- ' + c for c in unknowns)
            + '\n\nNo passing result, learned competence or launch approval is recorded by this revision.')
