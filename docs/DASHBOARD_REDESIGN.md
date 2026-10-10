# Dashboard redesign — UX-01

The owner requested a clearer, more attractive dashboard before BE-30. This increment introduces a forest and charcoal palette, grouped sidebar, per-view headings, consistent forms and an overview using actual loaded company records. It adds no synthetic business metrics.

Business research separates Research & practice, Run inspector and Executive skills. These sections remain mounted while switching their tabs, preserving the current practice draft. Navigating away from Business research retains the existing component lifecycle; this is not durable draft storage.

Mobile navigation supports opening, selecting a destination and closing with Escape. A navigation filter helps find views. Keyboard focus remains visible. Existing in-memory API-key handling and owner confirmation before live mode are preserved. Fonts and SVG icons are local; there are no new dependencies or external assets.

Design references: [Linear visual hierarchy](https://linear.app/now/behind-the-latest-design-refresh) and [Vercel grouped navigation](https://vercel.com/academy/optimize-your-vercel-account/tour-the-dashboard). The implementation uses original code and icons.

## Verification

Run `scripts/dashboard_design_smoke.py` with the checkout Python environment against the temporary production dashboard on port 3002. It checks every destination, loaded overview counts, business draft retention, navigation filtering, cancelled live-mode confirmation, desktop/mobile overflow and mobile Escape handling. Fixtures use disposable data and block external traffic. Existing run and skill browser checks also exercise the new tabs. Frontend lint and webpack production build validate the code; the existing image-performance lint warning is unrelated to this layout.

## Review locally

Stop your running app with Ctrl+C, then run `./company start` from the checkout. Open Overview and Business research. Your existing key, database and approval history are preserved. This change is awaiting owner review and does not merge or begin BE-30.
