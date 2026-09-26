# Ntheemba UI Usability Refactor Report

Status: `IMPLEMENTED / LOCAL SOURCE AND BROWSER VALIDATED`

## Routes

- `/operator/login`, `/operator`, `/operator/businesses`, `/operator/businesses/add`
- `/operator/businesses/{business_id}`, `/services`, `/channels`, and `/connections`
- `/operator/status`

The workspace is separate from `/dev/*`. It uses a server-side HttpOnly session
created after operator credential verification, CSRF-protected forms, and the
existing audited `OperatorControlPlaneService`; no second repository or UI
database was created. The UI never returns bearer tokens, auth references,
endpoint URLs, integration config, external session IDs, or channel IDs.

## Validation

- Focused: `python -m pytest -q tests/test_operator_ui.py tests/test_operator_control_plane_api.py` — 7 passed.
- Focused Ruff: `python -m ruff check ntheemba/api/routes/operator_ui.py ntheemba/main.py tests/test_operator_ui.py` — passed.
- Full suite: 588 passed, 2 skipped, 2 pre-existing failures in
  `tests/unit/infrastructure/test_postgres_migration_runner.py`; they expect
  migration 011 while the repository contains migration 012.
- Browser: local test-only FastAPI at `127.0.0.1:8765`, operator sign-in,
  Overview, Businesses, Business Detail, Business Services, and 390px service
  layout were exercised. Screenshots are under `output/playwright/`.

Visual-refinement focused run (2026-09-13):
`python -m pytest -q tests/test_operator_ui.py tests/test_operator_control_plane_api.py`
passed with 12 tests. Ruff passed for `ntheemba/api/routes/operator_ui.py`
and `tests/test_operator_ui.py`.

## Canonical local environment

The root Compose service now requires the dedicated
`NTHEEMBA_OPERATOR_API_TOKEN` and optionally accepts
`NTHEEMBA_OPERATOR_API_ALLOWED_ACTORS`. The actual uncommitted
`docker-compose.env` needs a distinct 32-character-or-longer token before the
canonical stack can be restarted with this UI. An NCPC, Control Centre, or
developer credential must not be reused.

## Remaining evidence limits

No production deployment, live external connection test, or live-data mutation
was performed. The browser test did not toggle a canonical business capability,
channel, or integration because those would mutate retained local configuration.

## Visual refinement (2026-09-13)

The separate operator workspace now has a modern responsive product shell:
a clear Ntheemba brand/header, restrained navy-violet visual system, elevated
status cards, accessible focus states, touch-sized actions, and a two-column
sign-in page that collapses to one column on small screens. The source keeps
the existing server-side session, CSRF, audit, authorization, and tenant
boundaries unchanged. `/dev/*` remains a protected developer surface rather
than an alternative operator UI.

## Deliverables

## Developer access and NCPC read diagnostics (2026-09-13)

Developer access uses the existing `/dev/login` form and its short-lived
HttpOnly session; it does not reuse the operator session or expose a token to
browser JavaScript. Root local Compose now admits Docker's private bridge to
the developer-session network gate while the application port stays bound to
loopback. After that network gate succeeds, a Docker bridge request may retain
its loopback browser origin, so the authenticated developer session remains
usable without admitting non-local origins. A direct browser visit to the POST-only `/dev/auth/session` endpoint
now redirects safely to `/dev/login`. The developer console now has an explicit
NCPC read-check control.
It invokes only the three identity operations Ntheemba consumes: candidate
search, variant lookup, and barcode lookup. It returns route names and
pass/fail states only; identities, barcodes, URLs, and credentials stay on the
server. Canonical-local validation passed all three checks after repairing the
existing least-privilege `local-ntheemba` reader digest.

## Deliverables

- `output/deliverables/Ntheemba_Apps_Updated.zip`
- `output/deliverables/Ntheemba_UI_Usability_Refactor_Patch.zip`
- `docs/NTHEEMBA-UI-UX-PLAYBOOK.md`
- `docs/NTHEEMBA-UI-INDEPENDENT-AUDIT-PROMPT.md`
