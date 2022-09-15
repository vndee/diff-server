-- WITH d AS (
-- 	SELECT updated_at - created_at as query_time FROM query_meta
-- ) SELECT sum(query_time)/COUNT(*) as average_query_time FROM d;
SELECT user_id, prompt, translated_prompt, updated_at, created_at, is_generated, query_id FROM query_meta ORDER BY created_at DESC LIMIT 10
