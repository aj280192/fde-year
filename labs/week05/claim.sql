-- A worker claims one queued task. Many workers can run this at once, and no two get the same task.
--
--   FOR UPDATE    locks the row the inner query picks, until this transaction ends.
--   SKIP LOCKED   if another worker has already locked a row, skip it and take the next one,
--                 instead of waiting: workers never queue behind each other.
--   RETURNING id  tells the worker which task it got, in the same statement.
--
-- Oldest first, with id as the tie-breaker. Saturday's partial index on queued tasks
-- (WHERE state = 'queued') makes the inner query fast on a million rows. Reused in capstone 3.

UPDATE tasks
SET state = 'running', updated_at = now()
WHERE id = (
    SELECT id
    FROM tasks
    WHERE state = 'queued'
    ORDER BY created_at, id
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id;