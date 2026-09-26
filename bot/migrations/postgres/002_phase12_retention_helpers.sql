BEGIN;

CREATE OR REPLACE FUNCTION cleanup_customer_memory(
    message_cutoff TIMESTAMPTZ,
    summary_cutoff TIMESTAMPTZ,
    question_cutoff TIMESTAMPTZ
) RETURNS TABLE (
    messages_deleted BIGINT,
    summaries_deleted BIGINT,
    questions_deleted BIGINT
) LANGUAGE plpgsql AS $$
DECLARE
    message_count BIGINT;
    summary_count BIGINT;
    question_count BIGINT;
BEGIN
    DELETE FROM conversation_messages WHERE created_at < message_cutoff;
    GET DIAGNOSTICS message_count = ROW_COUNT;

    DELETE FROM conversation_summaries WHERE created_at < summary_cutoff;
    GET DIAGNOSTICS summary_count = ROW_COUNT;

    DELETE FROM customer_questions WHERE created_at < question_cutoff;
    GET DIAGNOSTICS question_count = ROW_COUNT;

    messages_deleted := message_count;
    summaries_deleted := summary_count;
    questions_deleted := question_count;
    RETURN NEXT;
END;
$$;

INSERT INTO schema_migrations(version)
VALUES ('002_phase12_retention_helpers')
ON CONFLICT (version) DO NOTHING;

COMMIT;
