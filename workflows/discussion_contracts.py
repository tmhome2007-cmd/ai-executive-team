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
            'For critique, challenge unsupported statements rather than agreeing and recopying them. For revision, identify the specific change, or explicitly state no change is justified. '
            'Propose one reproducible next test with setup, observation and success/failure criteria rather than generic further testing. '
            'No tools, spending, implemented changes or owner consent are established by this discussion.')
