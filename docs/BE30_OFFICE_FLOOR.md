# BE-30 — first executive office floor

## Scope

Virtual office opens with a local CSS 3D perspective room: floor, walls, desk, screen, chair, rug, window and plant. Kai uses the existing saved character SVG and appearance metadata, including his specified identity. This is a flat portrait in a dimensional room, not a fully modelled character or virtual-life simulation. Existing 2D directory, inspector, workforce and recorded meetings remain available.

Camera angle and zoom are bounded controls with reset. Decorative movement is opt-in, never indicates reasoning, and pauses outside the viewport, when the tab is hidden and under reduced-motion preferences. It makes no inference requests. The room exposes an accessible text description and links to the CEO inspector.

State is derived only from loaded action records for `ceo`. An executing record shows its action ID; absence means no execution in the loaded snapshot, not company-wide live idle. Missing or stale data is Unknown. Animation grants no tools, spending, execution or approval authority.

## Asset and privacy review

All room geometry and styling are original repository code. The portrait reuses the existing approved identity renderer. No models, textures, external font, graphics library or dependencies were imported. No camera/microphone, tracking, cloud rendering or new data storage was added. This increment needs no new retention policy.

## Review

Stop the app with Ctrl+C and run `./company start`. Open Virtual office. Try camera angle, zoom, reset and decorative movement. Switch to 2D office directory, or Inspect CEO records. Full characters, walking employees and personal lives remain future work.

## Verification

Webpack production build and TypeScript passed. ESLint passed with the existing image-performance warning. The disposable Chromium dashboard smoke checks camera reset, reduced-motion controls, hidden-tab pause, 2D inspector, mobile overflow and existing navigation. Idle, executing and unknown states were checked against disposable API records. The local Chromium measurement gave a median frame interval of 16.7ms and p95 of 16.8ms across 60 intervals. Browser animation timing measurements are narrow local diagnostics, not a guarantee for every device; owner subjective smoothness review remains required.
