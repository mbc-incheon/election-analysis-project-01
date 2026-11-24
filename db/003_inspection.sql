-- Read-only inspection. sqlite3 CLI example: .read db/003_inspection.sql
PRAGMA foreign_key_check;
PRAGMA integrity_check;
SELECT 'snapshot' AS table_name, COUNT(*) AS row_count FROM snapshot
UNION ALL SELECT 'chunk', COUNT(*) FROM chunk
UNION ALL SELECT 'article', COUNT(*) FROM article
UNION ALL SELECT 'approval', COUNT(*) FROM approval
UNION ALL SELECT 'audit', COUNT(*) FROM audit;
SELECT id, status, json_extract(payload, '$.author') AS author,
       json_extract(payload, '$.snapshot_id') AS snapshot_id FROM article;
SELECT id, active, json_extract(payload, '$.candidate_id') AS candidate_id,
       json_extract(payload, '$.url') AS source_url FROM chunk;
-- Approval is deliberately not seeded; editorial approval must use the service API.
SELECT id, article_id, reviewer, reason, created_at FROM approval ORDER BY id;
