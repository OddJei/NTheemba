# Independent Ntheemba Operator UI Audit Prompt

Review the Ntheemba operator UI refactor independently. Do not modify files.

Verify that `/operator/*` is a plain-language operator workflow rather than a
renamed developer console; `/dev/console`, `/dev/simulator`,
`/dev/simulator/workspace`, and `/dev/pipeline` remain developer-only and
unchanged in meaning. Inspect the Overview, Businesses, Add Business, Business
Detail, Services, WhatsApp & Channels, Connections, System Status, Help, and
collapsed Technical details at desktop and 390px.

Confirm that ordinary screens do not expose bearer tokens, developer tokens,
NCPC tokens, auth references, endpoint URLs, integration config, external
session IDs, recipient identifiers, raw errors, or stack traces. Confirm that
the browser has no privileged storage, sessions are HttpOnly/SameSite, write
forms have CSRF protection, and every mutation goes through the existing
audited `OperatorControlPlaneService` with server-side capability and
business/channel ownership enforcement.

Check canonical capability labels map to the exact Ntheemba-owned IDs,
Marketplace/platform capability is unavailable in business UI, platform
channels cannot appear as business channels, connection state is not falsely
presented as a live health check, and pause/enable actions show consequences.

Return `ACCEPTED`, `ACCEPTED_WITH_LIMITATIONS`, or `BLOCKED`, including
reproducible route, viewport, and evidence for every finding. Do not call
source-only checks production proof.
