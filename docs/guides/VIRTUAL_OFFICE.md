# Virtual office — first version

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

The Virtual office dashboard view organizes the eleven existing executive roles into
three floors and five departments. Floors and avatars are presentation only; they do
not create employees, grant capabilities or change backend authority.

Select an executive to inspect their loaded action records, source decision IDs, measured
outcomes, outstanding resource requests and participation in recent meetings. Memory
links select that executive in Executive activity. The boardroom displays recent recorded
meetings, and the observation desk links to open follow-ups. Action, decision, resource
and follow-up links navigate to the existing review controls without making mutations.

Execution indicators reflect stored `executing` statuses only. There is no simulated
live presence or invented conversation. A meeting report is explicitly described as the
collective result, not an individual utterance. Records are bounded by the dashboard's
existing query limits; unavailable or stale data is marked accordingly. Refresh company
data updates the office. All text is rendered as React text without HTML execution.
No dependencies, external assets, trackers or persistent browser credentials were added.

## Verification

- Production build/TypeScript passed; lint has no errors and the existing screenshot
  image optimization warning remains.
- Native glob/Next lint contract passed; full npm audit reports zero vulnerabilities.
- Extended synthetic Chromium smoke passed: nine views, eleven profiles, floor filtering,
  CTO action/source-decision linkage, empty CFO state, executive memory selection,
  mobile layout, safe report rendering, unavailable/recovered API responses, authentication
  privacy and no mutation requests.
- Read-only production Chromium verification displayed existing local test meeting #6
  and its CEO participation in the office inspector.

Use the existing dashboard start instructions in COMPANY_DASHBOARD_V2.md, refresh the
browser and select Virtual office. Run `.venv/bin/python scripts/dashboard_smoke.py` from
the repository root while the dashboard built for API port 8001 is running.

Later additions can include persisted individual meeting messages and a real activity
stream. Those require backend records before the office can faithfully visualize them.
