BEGIN;

CREATE OR REPLACE FUNCTION cleanup_ntheemba_memory(
    message_cutoff TIMESTAMPTZ,
    summary_cutoff TIMESTAMPTZ,
    question_cutoff TIMESTAMPTZ,
    unsupported_cutoff TIMESTAMPTZ
) RETURNS TABLE (
    messages_deleted BIGINT,
    summaries_deleted BIGINT,
    questions_deleted BIGINT,
    unsupported_observations_deleted BIGINT
) LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    message_count BIGINT;
    summary_count BIGINT;
    question_count BIGINT;
    unsupported_count BIGINT;
BEGIN
    PERFORM set_config('app.system_maintenance', 'on', TRUE);
    DELETE FROM conversation_messages WHERE created_at < message_cutoff;
    GET DIAGNOSTICS message_count = ROW_COUNT;
    DELETE FROM conversation_summaries WHERE created_at < summary_cutoff;
    GET DIAGNOSTICS summary_count = ROW_COUNT;
    DELETE FROM customer_questions WHERE created_at < question_cutoff;
    GET DIAGNOSTICS question_count = ROW_COUNT;
    DELETE FROM unsupported_declarations WHERE last_observed_at < unsupported_cutoff;
    GET DIAGNOSTICS unsupported_count = ROW_COUNT;
    messages_deleted := message_count;
    summaries_deleted := summary_count;
    questions_deleted := question_count;
    unsupported_observations_deleted := unsupported_count;
    RETURN NEXT;
END;
$$;

INSERT INTO schema_migrations(version) VALUES ('002_phase12_retention')
ON CONFLICT (version) DO NOTHING;

COMMIT;
