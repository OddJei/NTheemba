# Phase 12.4 — Redis Session Repository

Sessions are serialized with a versioned allow-list rather than arbitrary pickle data. The codec supports Ntheemba domain dataclasses, enums, decimal values, dates, times, datetimes, bytes and immutable collections.

Redis session saves use optimistic revisions. A stale writer receives `SessionConflictError` instead of silently overwriting a newer conversation state.

Active and archived session TTLs are configured separately.
