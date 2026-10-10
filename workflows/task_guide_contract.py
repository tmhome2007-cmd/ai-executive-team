"""Render only approved task functions; model drafts example text and FAQs."""
import re
from pydantic import BaseModel, ConfigDict, Field
from memory.experiments import _text


class GuideFAQ(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question: str
    answer: str = Field(description='Explain the supplied create, edit or complete function. Only its UI controls are unknown; do not call the supplied function unavailable or unspecified.')


class TaskGuideDraft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    initial_task_text: str = Field(description='Only the initial fictional task text from supplied facts, for example Read chapter one. No instructions, field names or UI controls.')
    revised_task_text: str = Field(description='Only the changed fictional task text from supplied facts, for example Read chapter two. No instructions or UI controls.')
    faqs: list[GuideFAQ] = Field(min_length=3,max_length=3)
    unknowns: list[str] = Field(min_length=1,max_length=5)


def render_task_guide(raw, supplied_facts=''):
    draft=TaskGuideDraft.model_validate_json(raw)
    before=_text(draft.initial_task_text,'initial fictional task text',500)
    after=_text(draft.revised_task_text,'revised fictional task text',500)
    if before==after:
        raise ValueError('The fictional editing example must change the task text')
    if supplied_facts and (before.casefold() not in supplied_facts.casefold() or after.casefold() not in supplied_facts.casefold()):
        raise ValueError('Use the initial and revised task text supplied in the approved facts')
    # Function steps are rendered from the known domain operations, not inferred UI.
    # Label that intervention explicitly rather than presenting it as freeform AI prose.
    lines=['**Structured guide for the fictional task example**',
           'Function steps use the approved create, edit and complete operations. Example text and FAQ answers are AI-drafted and require owner review.',
           f'1. Use the create function to record the fictional task text “{before}”. Keep that task as the example for the following steps.',
           f'2. Identify the same fictional task, then use the edit function to change its text from “{before}” to “{after}”.',
           '3. After finishing the fictional activity, use the complete function on that same task to record its completion.',
           '**FAQ**']
    for faq in draft.faqs:
        question=re.sub(r'^(?:Q:\s*)+','',_text(faq.question,'FAQ question',500),flags=re.I)
        answer=re.sub(r'^(?:A:\s*)+','',_text(faq.answer,'FAQ answer',1000),flags=re.I)
        if not question or not answer: raise ValueError('Provide complete FAQ questions and answers')
        lines.extend(['Q: '+question,'A: '+answer])
    lines.append('**Unknowns**')
    for value in draft.unknowns:
        unknown=_text(value,'guide unknown',700)
        lines.append('- '+unknown+('' if 'unknown' in unknown.lower() else ' — unknown'))
    return '\n\n'.join(lines)
