# Company dashboard v2

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

The dashboard now presents the existing company backend through eight focused views:
Overview, Goals, Treasury, Decisions, Resources, Actions & results, Executive activity,
and System health. The overview links to the appropriate review surfaces; navigation
never approves, prepares, funds, grants access or executes anything.

The overview includes active goals in the loaded goal page, pending actions, outstanding
resource requests, open follow-ups, available/reserved capital per currency, recent
pending decisions and recorded outcomes. Decision and result summaries explicitly cover
the latest 20 records; goal and follow-up views currently load up to 100 rows. These are
loaded-record summaries, not a claim of complete company-wide aggregate statistics.
Unknown or failed loads are marked unavailable. Failed refreshes preserve existing data
with a stale-data warning. Refresh retries all views and the health endpoint.

Existing controls remain available in their corresponding views, including goal lineage,
decision lineage, resource approval/fulfillment, treasury funding, meeting types, action
approval/execution, outcome editing, memory review and autonomous follow-up. Switching
views preserves draft forms. The API key remains in React memory only and reload requires
re-entry. Model reports render basic headings, bold text and list items as React text;
HTML, scripts and links are never executed. No new runtime dependencies were added.

## Local preview

Keep the isolated backend running on 127.0.0.1:8001 with its existing test configuration.
From `executive-dashboard`, run:

```bash
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8001 npm run build -- --webpack
npm run start -- --hostname 127.0.0.1
```

Open http://127.0.0.1:3000 in a normal browser and enter the local test API key.

## Verification

- Production webpack build and TypeScript: passed.
- ESLint: no errors; existing authenticated screenshot image optimization warning remains.
- Native glob/Next lint contract: passed.
- Full npm audit: zero vulnerabilities.
- Disposable foundation regression: 150/150 passed.
- Chromium synthetic smoke: all eight views, safe report rendering, failed/recovered
  treasury responses, mobile width, memory-only authentication and no mutation requests.
- Production dashboard connected to the existing local test API in Chromium, read-only.
- The Codex in-app browser preview reported fetch failures despite the successful normal
  Chromium check and API/CORS responses; normal browser preview is verified.

Run the browser smoke from the repository root after starting the dashboard built for API
port 8001:

```bash
.venv/bin/python scripts/dashboard_smoke.py
```

The smoke replaces API responses with synthetic data and checks navigation only. It does
not duplicate the existing backend approval/execution regression suite or initiate model
meetings, external actions, funding, resource fulfillment or notifications.
