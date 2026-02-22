Migration notes: platform_fee refactor
===================================

Summary
-------
This release defers creation of `platform_fees` rows until delivery confirmation
and records per-refund `platform_fee_minor` on `pawapay_refunds` instead of
mutating original deposits. Gross revenue is computed from `platform_fees`
minus refunded platform fees (refunds reference original deposit/order).

DB changes required
-------------------
- Add `platform_fee_minor` integer column to `pawapay_refunds` with default 0.

Example SQL migration (Postgres):

```sql
ALTER TABLE public.pawapay_refunds
  ADD COLUMN IF NOT EXISTS platform_fee_minor integer NOT NULL DEFAULT 0;

-- Optional index to speed queries joining refunds -> platform_fees by deposit_id/order_id
CREATE INDEX IF NOT EXISTS ix_pawapay_refunds_deposit_id ON public.pawapay_refunds (deposit_id);
CREATE INDEX IF NOT EXISTS ix_platform_fees_deposit_id ON public.platform_fees (deposit_id);
```

Deployment notes
----------------
- Deploy `payment-revenue` and `order-delivery` services together to avoid lost delivery events.
- Run DB migration before routing real traffic.
- After deployment, existing deposits will not automatically have a `platform_fees` row until
  the order-delivery service emits the delivery event (outbox or manual replay may be used).

Testing
-------
- Use the included test template `tests/test_platform_fee_flow.py` to write integration tests.

Monitoring
----------
- Monitor logs for `platform_fee_inserted`, `platform_fee_already_exists`,
  `platform_fee_insert_integrity_error`, and `persisted_refund_platform_fee` to ensure
  correct behavior during rollout.
