-- Initial SQL migration (Postgres) for bots, sessions, events

-- Enums
DO $$ BEGIN
    CREATE TYPE bot_type AS ENUM ('default', 'custom');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE session_mode AS ENUM ('public', 'registered', 'customer', 'staff');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE session_status AS ENUM ('active', 'inactive');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS bots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone_number TEXT UNIQUE NOT NULL,
  type bot_type NOT NULL,
  business_id UUID,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  user_phone TEXT NOT NULL,
  bot_id UUID NOT NULL REFERENCES bots(id),
  business_id UUID,
  bot_type bot_type NOT NULL,
  session_mode session_mode NOT NULL,
  platform TEXT NOT NULL,
  current_node TEXT,
  last_event_id UUID,
  object_context JSONB,
  status session_status NOT NULL DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_user_phone_bot_platform ON sessions (user_phone, bot_id, platform);
CREATE INDEX IF NOT EXISTS ix_sessions_user_phone ON sessions (user_phone);
CREATE INDEX IF NOT EXISTS ix_sessions_platform ON sessions (platform);

CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id),
  user_phone TEXT,
  user_id UUID,
  bot_id UUID NOT NULL,
  last_event_id UUID,
  message_count INTEGER DEFAULT 1,
  event_type TEXT,
  payload_events JSONB,
  previous_turns JSONB,
  status TEXT,
  updated_fields JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
