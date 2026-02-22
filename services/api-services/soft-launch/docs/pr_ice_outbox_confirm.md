Title: ICE — Authoritative Outbox Write for Confirm (feature/ice-outbox-confirm)

Summary
-------

Add an endpoint to `ICE` that writes an `ice.confirmed` Outbox row inside the same DB transaction used to persist authoritative session/order state. This is the Phase 2 change from the refactor roadmap — it makes ICE Outbox-first while preserving existing Redis sinks (TODO: mirror Redis for compatibility).

Files changed
-------------

- `services/ice/src/app/main.py` — add `/sessions/{session_id}/confirm` endpoint that creates `Outbox` ORM row.
- `services/ice/tests/test_confirm_endpoint.py` — unit test verifying the endpoint creates an outbox row and returns `outbox_id`.

Testing
-------

Run the ICE unit test locally (ensure venv activated):

```bash
pytest -q services/ice/tests/test_confirm_endpoint.py
```

Notes / Migration
-----------------

- This keeps existing Redis stream sinks; next PR should add mirroring to Redis for compatibility and a feature flag for Outbox-first rollout.
- The Outbox model used by ICE is `services/ice/src/app/models.py` (table `outbox`).

How to push & open PR
---------------------

1. Create branch locally and commit (already done locally by this change):

```bash
git checkout -b feature/ice-outbox-confirm
git add -A
git commit -m "ICE: add /sessions/{session_id}/confirm endpoint to write Outbox row; add unit test"
```

1. Push and open PR on GitHub:

```bash
git push -u origin feature/ice-outbox-confirm
# then open PR in the repo's GitHub UI using the pushed branch
```
