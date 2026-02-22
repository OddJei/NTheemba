-- Migration: create canonical public.outbox table
-- Run this on Postgres. Requires privileges to create extension or use uuid generation.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.outbox (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic text NOT NULL,
  destination text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  headers jsonb,
  producer text,
  correlation_id text,
  dedupe_key text,
  status text NOT NULL DEFAULT 'pending',
  attempts integer NOT NULL DEFAULT 0,
  last_error text,
  scheduled_at timestamptz,
  priority integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_outbox_status_created ON public.outbox (status, created_at);
CREATE INDEX IF NOT EXISTS ix_outbox_dedupe_key ON public.outbox (dedupe_key);
CREATE INDEX IF NOT EXISTS ix_outbox_scheduled_at ON public.outbox (scheduled_at);

-- Trigger to update `updated_at` automatically
CREATE OR REPLACE FUNCTION public.outbox_update_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_outbox_updated_at ON public.outbox;
CREATE TRIGGER trg_outbox_updated_at
BEFORE UPDATE ON public.outbox
FOR EACH ROW EXECUTE FUNCTION public.outbox_update_updated_at();
