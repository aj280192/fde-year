# Use the Index, Luke · cheat sheet

[use-the-index-luke.com](https://use-the-index-luke.com/) by Markus Winand. Read Tue 3 Nov 2026: *Anatomy of an SQL Index*, *The Where Clause*, *The Join Operation*. Used this week for the task tables (Wed), the million-row lab (Sat) and the health RAG queries.

---

## Three questions

**1. Why is an index lookup fast?**
A B-tree index keeps a sorted copy of the column's values, each with a pointer to its table row (in Postgres, the `ctid`). The leaves are linked to each other in order, and the branch nodes above hold the largest value of each node below, up to a single root. Each node holds hundreds of entries, so even millions of rows need only 3 to 5 levels, and every leaf is at the same depth (that's what "balanced" means; the database keeps it that way on every insert).

A lookup has three parts:
1. walk down the tree: always fast, 3 to 5 steps
2. walk along the leaf chain, if many entries match
3. fetch each matching row from the table

When an index lookup is slow, it's nearly always parts 2 and 3, not the tree.

**2. Why does column order matter in a multi-column index?**
In an index on `(emp_id, dep_id)`, entries are sorted by `emp_id`, and `dep_id` is in order only within each `emp_id`. So the rows for one `dep_id` are scattered across the whole index, and a query on `dep_id` alone can't use it for a narrow lookup.

- An index can be used for its **leading columns**: `(a, b)` serves `WHERE a = …` and `WHERE a = … AND b = …`, but not `WHERE b = …` alone.
- **Put equality columns first, and range or sort columns last**, so one index serves the most queries.
- One index on `(tenant_id, created_at)` makes a separate index on `tenant_id` unnecessary.

**3. When does a join use an index, and when does it hash?**
It depends mostly on **how many rows are joined**, not only on whether an index exists.

| Join | How it works | Uses an index? | Best when |
| --- | --- | --- | --- |
| Nested loops | for each row on one side, look up its matches on the other | yes, on the other table's join column | few rows come from the first side |
| Hash join | load the smaller side into an in-memory hash table, then scan the other side once | not on the join columns | many rows are joined |
| Merge join | sort both sides by the join key, then walk them together | can use one, to skip the sort | both sides are already sorted |

The database often picks a hash join **even when an index exists**: for 100,000 matches, 100,000 separate index lookups and table fetches cost more than building one hash table and scanning once. To help a hash join, index the **`WHERE` filters**, so less is hashed, not the join columns, and select only the columns you need, so the hash table fits in memory.

---

## Rules to remember

- **Functions defeat indexes.** `WHERE lower(email) = …` can't use an index on `email`, because the index stores the original values. Either index the expression, `CREATE INDEX … ON t (lower(email))`, or rewrite the condition so the column stands alone.
  - The same goes for `WHERE created_at::date = '2026-11-03'`: write it as a range, `created_at >= '2026-11-03' AND created_at < '2026-11-04'`.
- **`LIKE 'abc%'` can use an index; `LIKE '%abc'` can't.** Only a known start of the string narrows the search.
- **Index-only scan:** if the index holds every column the query needs, the table is never read. That's the cheapest plan there is.
- **More indexes aren't free.** Every insert and update must also update each index, so add the ones your real queries need, and no more.
- **Statistics matter.** The planner chooses a plan from estimated row counts. After loading a lot of data, run `ANALYZE` (or `VACUUM ANALYZE`), or the estimates are wrong and so is the plan.

## Reading `EXPLAIN` in Postgres

| Plan line | Means |
| --- | --- |
| `Seq Scan` | reads every row of the table; fine for small tables or when most rows match |
| `Index Scan` | walks the index, then fetches each matching row from the table |
| `Index Scan Backward` | the same, reading the index in reverse: this is how `ORDER BY … DESC` avoids a sort |
| `Bitmap Index Scan` + `Bitmap Heap Scan` | collects matching row positions from the index first, then reads the table in physical order; used when "quite a few" rows match |
| `Index Only Scan` | answers from the index alone, never touching the table |
| `Sort` | an explicit sort step; disappears when an index already provides the order |
| `rows=` | the planner's **estimate** of rows at that step; a big gap from reality means stale statistics |

- `EXPLAIN` shows the plan without running the query.
- `EXPLAIN ANALYZE` runs it and adds real times and real row counts.
- `EXPLAIN (ANALYZE, BUFFERS)` also shows how many pages were read: Saturday's lab uses this.

---

## My three examples

On a 50,000-row `tasks` table, in Postgres 17 (Docker, `pgvector/pgvector:pg17`), after `VACUUM ANALYZE`.

> Fill in the "What I saw" column from your own `EXPLAIN` output, and replace any expectation that turned out different.

| # | Query | Index | Expected first plan line |
| --- | --- | --- | --- |
| 1a | `WHERE lower(email) = 'user42@example.com'` | on `email` | `Seq Scan`: the function defeats the index |
| 1b | the same | on `lower(email)` | `Index Scan` or `Bitmap Index Scan` |
| 2a | `WHERE tenant_id = 7 ORDER BY created_at DESC LIMIT 20` | on `(tenant_id, created_at)` | `Index Scan Backward`, with no `Sort` |
| 2b | `WHERE created_at > now() - interval '1 hour'` | the same | `Seq Scan` or a full index scan: `created_at` isn't the leading column |
| 3a | `SELECT tenant_id, created_at … WHERE tenant_id = 7` | the same | `Index Only Scan` |
| 3b | `SELECT tenant_id, created_at, status … WHERE tenant_id = 7` | the same | `Index Scan` or `Bitmap`: `status` isn't in the index |

**What this means for my task API:** query 2a **is** the `list_tasks` query: one owner, newest first, one page. So the index Wednesday adds is `(tenant_id, created_at)`. Ordering by `created_at` and `id` together exactly, to match the cursor's tie-breaker, would need `(tenant_id, created_at, id)`, which I'll check with `EXPLAIN` on Saturday.