"""Fixed, phase-specific published discussion contracts, separate from strategy meetings."""
CONTRACTS = {
    'proposal': 'Evidence and gaps; Proposed next test; Expected observation; Owner review requested',
    'critique': 'Claims challenged; Why the supplied evidence does not support them; Test improvements; Remaining unknowns',
    'revision': 'Changes made in response to critique; Revised next test; What remains unknown; Owner review requested',
    'synthesis': 'Supported findings; Unresolved questions; Recommended next test and observable result; Owner approval pending',
}


def round_contract(phase, solo):
    if phase not in CONTRACTS or type(solo) is not bool:
        raise ValueError('Invalid discussion round contract')
    mode = ('This is single-executive self-review. Critique your own prior proposal. There are no inter-executive disagreements; missing evidence is an unresolved question, not a disagreement.' if solo else
            'Review other published views critically. Report disagreement only by naming the executives and their actual incompatible recommendations; uncertainty alone is not disagreement.')
    return (mode + '\nUse ONLY these headings, in order: ' + CONTRACTS[phase] + '.\n'
            'Keep the response under 250 words. Do not repeat the full previous response or reuse the general strategy-meeting template. '
            'Ground findings in the supplied evidence/source IDs. Prior speeches and remembered company facts are not new evidence. '
            'Do not introduce product launches, revenue loss, market share, customer behavior, competitive positioning or assumed budgets unless current source records establish their relevance. '
            'A fictional test remains fictional. Persona influences judgment and tone, not invented facts; do not add a Preserving Personality section. '
            'For critique, cite every challenged claim on a separate line in the exact form Claim quote: executive_key | verbatim published text. Quote only the published proposal, never raw drafts or review cues. If it already blocks the test, acknowledge that; do not claim it permits running or guessing. No change needed is valid. For revision, identify the specific change, or explicitly state no change is justified. '
            'Propose one reproducible next test with setup, observation and success/failure criteria rather than generic further testing. '
            'For proposal, revision and synthesis, include these labelled lines: Prerequisites:, Setup:, Steps:, Observe:, Pass:, Fail:, Causal limit:. '
            'Prerequisites must name missing original reproduction steps, reminder due time, build and observation channel; if these are unknown, block the test until supplied instead of inventing values. '
            'When any prerequisite is missing, write Setup: Blocked; Steps: Do not run; Observe: Not scheduled; Pass: Not assessable; Fail: Not assessable. Never use an if-known fallback, variable due time or invented delay. Request the missing details only. '
            'Steps must describe ordered operations, what stays fixed and what variable changes. Observe must identify the recorded artifact or event and its time window. '
            'Pass/Fail refer only to the stated observation under the chosen conditions; state expected results as hypotheses, not promised outcomes. '
            'Causal limit must explicitly say a passing or failing reminder test does not alone identify the cause; a controlled comparison is needed to isolate a factor. '
            'Do not recommend examining account settings, external services or any other subsystem whose existence/relevance is not established by supplied evidence. Ask for original reproduction details before choosing a subsystem. '
            'Do not describe a hypothetical passing result as proof that a system component is healthy or that a particular configuration caused the original failure. '
            'No tools, spending, implemented changes or owner consent are established by this discussion.')

TEST_FIELDS = ('Prerequisites', 'Setup', 'Steps', 'Observe', 'Pass', 'Fail', 'Causal limit')


def assess_round(body, phase, evidence):
    """Narrow deterministic review cues, not semantic truth/causality certification."""
    import re
    warnings = []
    normalized = {re.sub(r'[*#_:]', '', line).strip().lower() for line in body.splitlines()}
    for heading in CONTRACTS[phase].split('; '):
        if heading.lower() not in normalized:
            warnings.append('Missing round section: ' + heading)
    if phase in {'proposal', 'revision', 'synthesis'}:
        for field in TEST_FIELDS:
            if not re.search(r'(?im)^\s*(?:-\s*)?' + re.escape(field) + r'\s*:', body.replace('*', '').replace('_', '')):
                warnings.append('Missing test detail: ' + field)
    for name, pattern in (
        ('account settings', r'\b(?:user\s+)?account\s+settings?\b'),
        ('external services', r'\bexternal\s+services?\b'),
        ('revenue', r'\b(?:revenue|earnings)\b'),
        ('market share', r'\bmarket\s+share\b'),
    ):
        source_sentences = re.split(r'[.!?\n]', evidence)
        established = any(re.search(pattern, s, re.I) and not re.search(r'\b(no|not|unknown|unsupported|fictional|synthetic|missing|without)\b', s, re.I) for s in source_sentences)
        if established:
            continue
        output_sentences = re.split(r'[.!?\n]', body)
        # Explicitly declining an invented dependency is appropriate. Questions,
        # conditionals and investigative instructions can still introduce it.
        introduced = any(re.search(pattern, s, re.I) and not re.search(r'\b(?:no|not established|not supplied|not provided|do not assume|cannot assume)\b', s, re.I) for s in output_sentences)
        if introduced:
            warnings.append('Unestablished context introduced: ' + name)
    causal_claim = r'\b(?:proves?|confirms?|establish(?:es)?)\s+(?:the\s+)?(?:root\s+)?cause\b'
    negative_claim = r"\b(?:not|never|cannot|doesn.t|without)\b.{0,60}\b(?:proves?|confirms?|establish(?:es)?)\b"
    if any(re.search(causal_claim, sentence, re.I) and not re.search(negative_claim, sentence, re.I)
           for sentence in re.split(r'[.!?\n]', body)):
        warnings.append('Causal claim needs a controlled comparison; an observed pass alone does not prove cause')
    return {'version': 1, 'status': 'review_required' if warnings else 'checks_passed', 'warnings': warnings,
            'scope': 'Heuristic section/dependency checks only; no independent truth or causal verification'}


def guard_missing_prerequisites(body, phase):
    """Replace an executable-looking test when its own text admits missing inputs."""
    import re
    if phase not in {'proposal', 'revision', 'synthesis'}:
        return body
    sentences = re.split(r'[.!?\n]', body)
    missing = any(re.search(r'original reproduction|reminder due time|observation channel|\bbuild\b', sentence, re.I)
                  and re.search(r'unknown|not provided|not supplied|missing|does not (?:include|provide|specify)|still needed', sentence, re.I)
                  for sentence in sentences)
    if not missing:
        return body
    test_heading = {'proposal': 'Proposed next test', 'revision': 'Revised next test',
                    'synthesis': 'Recommended next test and observable result'}[phase]
    headings = CONTRACTS[phase].split('; ')
    lines = body.splitlines()
    normalized = [re.sub(r'[*#_:]', '', line).strip().lower() for line in lines]
    start = next((i for i, line in enumerate(normalized) if line == test_heading.lower()), None)
    blocked = ('Prerequisites: Obtain the original reproduction steps, reminder due time, build and observation channel.\n'
               'Setup: Blocked until these missing details are supplied.\n'
               'Steps: Do not create a task, choose a substitute due time or run the test. Request the missing details.\n'
               'Observe: Not scheduled until the reproduction conditions and observation window are defined.\n'
               'Pass: Not assessable before prerequisites are supplied and the test is defined.\n'
               'Fail: Not assessable before prerequisites are supplied and the test is defined.\n'
               'Causal limit: A future passing or failing observation alone does not establish cause.')
    if start is None:
        # Malformed output cannot safely retain an executable-looking proposal.
        return '\n\n'.join('**' + heading + '**\n' + (blocked if heading == test_heading else
                              'Test blocked: missing reproduction details. No execution or owner approval is recorded.')
                              for heading in headings)
    stop = next((i for i in range(start + 1, len(lines)) if normalized[i] in [h.lower() for h in headings]), len(lines))
    lines[start + 1:stop] = ['', blocked, '']
    if phase == 'proposal':
        normalized = [re.sub(r'[*#_:]', '', line).strip().lower() for line in lines]
        observation = next((i for i, line in enumerate(normalized) if line == 'expected observation'), None)
        if observation is not None:
            end = next((i for i in range(observation + 1, len(lines)) if normalized[i] in [h.lower() for h in headings]), len(lines))
            lines[observation + 1:end] = ['', 'No observation is scheduled while the prerequisites are missing.', '']
    return '\n'.join(lines)


def guard_critique_references(body, proposals):
    """Verify quotation attribution; discard uncited or fabricated critiques."""
    import re
    clean = body.replace('**', '')
    citations = re.findall(r'(?im)^\s*Claim quote:\s*([a-z_]+)\s*\|\s*(.+?)\s*$', clean)
    def normalized(text):
        return ' '.join(text.replace('**', '').split())
    valid = bool(citations) and all(len(quote.strip()) >= 12 and role in proposals
                                  and normalized(quote) in normalized(proposals[role])
                                  for role, quote in citations)
    if valid:
        return body
    blocked = any('Setup: Blocked' in proposal.replace('**', '') for proposal in proposals.values())
    acknowledgement = ('The published proposal already blocks the test and requests missing details. '
                       'No new blocking change is needed.' if blocked else
                       'No challenge with a verified quotation was supplied. Review the published proposals directly.')
    return ('**Claims challenged**\nNo verified challenge is recorded. The generated critique lacked valid published-claim quotations.\n\n'
            '**Why the supplied evidence does not support them**\nUnverified attributions were withheld; prior speeches are not source evidence.\n\n'
            '**Test improvements**\n' + acknowledgement + '\n\n'
            '**Remaining unknowns**\nNo additional facts or executed tests are established by this critique.')


def guard_revision_changes(body, original):
    """Do not present an existing blocked test as a newly implemented change."""
    import re
    if 'Setup: Blocked' not in original.replace('**', ''):
        return body
    lines = body.splitlines()
    headings = CONTRACTS['revision'].split('; ')
    normalized = [re.sub(r'[*#_:]', '', line).strip().lower() for line in lines]
    start = next((i for i, line in enumerate(normalized) if line == headings[0].lower()), None)
    if start is None:
        return body
    end = next((i for i in range(start + 1, len(lines)) if normalized[i] in [h.lower() for h in headings]), len(lines))
    lines[start + 1:end] = ['', 'The published proposal already blocked the test and requested the missing details. '
                             'Retaining that stop condition is not a new change. No additional change is verified here.', '']
    return '\n'.join(lines)
