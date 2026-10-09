"""Bounded service hypotheses and source-exact quotes; no inferred market facts."""
import json
import re
from memory.experiments import _text

SERVICES = {
    'documentation': 'Documentation service: draft setup guides and FAQs',
    'editing': 'Editing service: improve owner-supplied text',
    'support_drafts': 'Support drafting service: draft replies from supplied policies',
}
VERSION = 2


def research_instruction():
    return ('Compare these service hypotheses only: ' + json.dumps(SERVICES) + '. They are candidate deliverables, not verified opportunities. '
        'Cloudflare and GitHub are hosting/tools; Fiverr is a marketplace, never a deliverable. Do not infer a restriction on one platform applies to others. '
        'Return JSON only: {"options":[{"key":"documentation","skills":["..."],"exercise":"...","checks":["...","..."]}, ...],'
        '"practice_choice":"documentation"}. '
        'Include exactly all three keys. Use 2–5 observable checks per option. Exercises must produce private text samples without new access or spending. '
        'practice_choice selects a useful learning exercise only, never the best business or a demand finding. Do not generate quotations; the server attaches registered source excerpts separately. '
        'No claims about commercial permission, demand, prices, earnings, existing skills or achievements. Missing evidence stays unknown; no prose outside JSON.\n')


def render_research(raw, sources):
    try:
        payload = json.loads(raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip())
    except (ValueError, AttributeError):
        raise ValueError('Research failed the structured comparison check; no practice plan is ready') from None
    if not isinstance(payload, dict) or set(payload) != {'options', 'practice_choice'}:
        raise ValueError('Research must separate service comparisons from exact source excerpts')
    options = payload['options']
    if not isinstance(options, list) or len(options) != 3 or any(not isinstance(o, dict) for o in options):
        raise ValueError('Research must compare three deliverable services')
    if any(set(o) != {'key', 'skills', 'exercise', 'checks'} for o in options):
        raise ValueError('Research option fields are incomplete')
    if any(not isinstance(o['key'], str) for o in options) or {o['key'] for o in options} != set(SERVICES):
        raise ValueError('Hosting platforms and marketplaces are tools, not business options')
    if not isinstance(payload['practice_choice'], str) or payload['practice_choice'] not in SERVICES:
        raise ValueError('Invalid practice choice')
    for option in options:
        option['exercise'] = _text(option['exercise'], 'practice exercise', 2000)
        for field in ('skills', 'checks'):
            values = option[field]
            minimum = 2 if field == 'checks' else 1
            if not isinstance(values, list) or not minimum <= len(values) <= 5:
                raise ValueError('Every service needs skills and observable practice checks')
            option[field] = [_text(v, field, 500) for v in values]
        text = json.dumps(option)
        if re.search(r'(?:not (?:intended|allowed|permitted|suitable) for commercial|(?:prohibit|ban|forbid)\w* commercial|commercial use (?:is )?(?:prohibited|forbidden|banned))', text, re.I):
            raise ValueError('Unsupported commercial-use claims withheld; quote source restrictions separately')
    lines = ['**Findings**', 'Three proposed services were compared as learning hypotheses. None is a verified business opportunity.',
             '**Unknowns**', 'Customer demand, market size, pricing, contingent fees, commercial eligibility and agent competence remain unknown.',
             'The supplied platform/hosting records alone do not establish buyer demand. No best business can be selected from these records alone.',
             '**Next action**', 'Practice candidate only: ' + SERVICES[payload['practice_choice']] + '. Owner selection and sample review are still required.',
             '**Service comparisons — proposed practice, not demonstrated skills**']
    for option in options:
        lines.extend(['\n' + SERVICES[option['key']], 'Required skills — unproven: ' + '; '.join(option['skills']),
                      'Private practice deliverable: ' + option['exercise'], 'Model-suggested checks — refine vague criteria before owner approval:'])
        lines.extend('- ' + check for check in option['checks'])
        controls = {
            'documentation': ['Every described feature matches the supplied or explicitly fictional brief', 'Missing feature details are labelled unknown', 'A reader can follow the stated steps without invented credentials or accounts'],
            'editing': ['The original supplied facts are preserved', 'Identified spelling/grammar errors are corrected', 'No new promises, performance claims or facts are introduced'],
            'support_drafts': ['Every proposed answer matches the supplied or explicitly fictional policy', 'Missing policy details are escalated for owner review', 'The draft never claims a refund, approval or other action has happened'],
        }
        lines.append('Minimum review controls:')
        lines.extend('- ' + check for check in controls[option['key']])
        lines.extend(['Practice input: supply a short brief/text/policy, or use a clearly labelled fictional fixture.',
                      'Access: no external account is needed for private text practice. Real delivery access has not been assessed.',
                      'Owner responsibilities: choose the exercise and review its sample; professional skills are not assumed.',
                      'Authorized spending/loss: €0. Execution, delivery and future costs are not established.'])
    lines.append('\n**Source excerpts — apply only to their own source; not independent verification**')
    for source in sources:
        # The excerpt comes from the immutable record, never a model attribution.
        excerpt = source['summary'][:400]
        lines.append(f"Source #{source['id']} — {source['title']} — {source['reference']} — observed {source['observed_at']} — {source['freshness']} / {source['verification']}\nOpening excerpt (may be incomplete): {excerpt}")
    return '\n\n'.join(lines)


from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ResearchOption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: Literal['documentation', 'editing', 'support_drafts']
    skills: list[str] = Field(min_length=1, max_length=5)
    exercise: str
    checks: list[str] = Field(min_length=2, max_length=5)


class ResearchComparison(BaseModel):
    model_config = ConfigDict(extra='forbid')
    options: list[ResearchOption] = Field(min_length=3, max_length=3)
    practice_choice: Literal['documentation', 'editing', 'support_drafts']
