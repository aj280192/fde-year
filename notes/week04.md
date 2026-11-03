# Week 4 · 26 Oct to 1 Nov 2026 · API design

This week's note is a quick-start guide for engineers calling the agent task API for the first time. The design behind it is in [labs/week04/DESIGN.md](../labs/week04/DESIGN.md), and the code is in [labs/week04](../labs/week04).

> **Before publishing:** run `serve.py` and replace every response below with the real output from your own calls. The ids and times shown are examples.

---

# Agent task API · quick start (v1)

## What it does

You give the API a piece of work for an AI agent, such as *"diagnose why the payments pods are crash-looping"*, and get a task id back straight away. The agent works in the background. You check on the task whenever you like, until it reaches a final state: `succeeded`, `failed` or `cancelled`.

It works this way because agent work takes minutes, not seconds, and may pause to ask a question. You never have to hold a connection open, and nothing is lost if your connection drops.

## Before you start

You need an **API key**, which looks like `sk_...`. Keep it secret: anyone holding it can act as you.

```bash
export KEY=sk_...                     # your key
export API=http://localhost:8000      # where the API runs
```

Every request sends the key in the `X-API-Key` header. A key has one or both permissions:

| Permission | Lets you |
| --- | --- |
| `tasks:read` | get a task, list your tasks |
| `tasks:write` | create a task, cancel a task |

You only ever see **your own** tasks. Another key's task looks exactly like one that doesn't exist.

## Your first task

**1 · Create it**

```bash
curl -s -X POST "$API/v1/tasks" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "Diagnose: payments pods crash-looping in namespace payments"}'
```

The answer comes back at once, with status **202 Accepted**: the work has been accepted, not finished.

```json
{
  "id": "t_Qx3vL9pT2mKa8YdN1rB7cw",
  "state": "queued",
  "input": "Diagnose: payments pods crash-looping in namespace payments",
  "result": null,
  "error": null,
  "created_at": "2026-11-03T14:05:11Z",
  "updated_at": "2026-11-03T14:05:11Z"
}
```

Keep the `id`. `input` is the only field you can set; sending any other field (such as `state`) is rejected.

**2 · Check on it**

```bash
curl -s "$API/v1/tasks/t_Qx3vL9pT2mKa8YdN1rB7cw" -H "X-API-Key: $KEY"
```

This returns the same shape, with the current `state`. When the state is `succeeded`, the answer is in `result`. When it's `failed`, the reason is in `error`.

**3 · Cancel it** (if you no longer need it)

```bash
curl -s -X POST "$API/v1/tasks/t_Qx3vL9pT2mKa8YdN1rB7cw:cancel" -H "X-API-Key: $KEY"
```

This returns the task with `"state": "cancelled"`. **Cancelling twice is safe**: the second call returns the same task, unchanged.

**4 · List your tasks**

```bash
curl -s "$API/v1/tasks?page_size=2" -H "X-API-Key: $KEY"
```

```json
{
  "tasks": [ { "id": "t_...", "state": "queued", "...": "..." }, { "...": "..." } ],
  "next_page_token": "eyJ0IjogIjIwMjYtMTEtMDNUMTQ6MDU6MTFaIiwgImlkIjogInRfLi4uIn0="
}
```

## Task states

```text
queued ──► running ──► succeeded
  │          │  ▲
  │          ▼  │
  │   waiting_for_input
  │          │
  └──────────┴──► failed or cancelled
```

| State | Meaning | Final? |
| --- | --- | --- |
| `queued` | accepted, waiting for the agent to start | no |
| `running` | the agent is working | no |
| `waiting_for_input` | the agent has asked a question and is paused | no |
| `succeeded` | finished; the answer is in `result` | yes |
| `failed` | stopped with an error; the reason is in `error` | yes |
| `cancelled` | stopped because you cancelled it | yes |

**Stop polling when a task reaches a final state.** It never changes after that.

## Retrying safely

If your connection drops while creating a task, you can't tell whether it was created. Send an **`Idempotency-Key`** header, a unique string you choose for each new task, and retry with the **same** key:

```bash
curl -s -X POST "$API/v1/tasks" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: deploy-4521-diagnosis" \
  -d '{"input": "Diagnose: payments pods crash-looping in namespace payments"}'
```

| If you send | You get |
| --- | --- |
| the same key and the same body, within 24 hours | **the same task**, not a new one, with the response header `Idempotent-Replayed: true` |
| the same key with a different body | an error, `IDEMPOTENCY_KEY_REUSED`: use a new key for new work |
| the same key after 24 hours | a new task |

The key must be 1 to 255 characters. Keys are private to your API key, so another client using the same string doesn't affect you.

## Paging through your tasks

Tasks come back **newest first**.

- `page_size`: how many per page, between 1 and 100 (20 if you leave it out).
- `page_token`: leave it out for the first page. For the next page, send the `next_page_token` from the previous response, exactly as you received it.
- **Stop when `next_page_token` is empty.** A page with fewer tasks than `page_size` doesn't by itself mean it's the last one.

Treat the token as an opaque string: don't build or edit one. Tasks created while you're paging don't cause duplicates or gaps in the pages you're reading.

## Errors

Every error has the same shape:

```json
{
  "error": {
    "code": 404,
    "status": "NOT_FOUND",
    "message": "Task 't_9999' does not exist.",
    "details": [{ "reason": "TASK_NOT_FOUND" }]
  }
}
```

**Write your code against `reason`**, which never changes. `message` is for people, and its wording may change.

| HTTP | `reason` | What it means | What to do |
| --- | --- | --- | --- |
| 401 | `API_KEY_INVALID` | no `X-API-Key` header, or the key isn't recognised | check the header name and the key |
| 403 | `INSUFFICIENT_PERMISSION` | your key can't do this action, for example a read-only key creating a task | use a key with `tasks:write` |
| 404 | `TASK_NOT_FOUND` | no such task, or it isn't yours | check the id; you can only see your own tasks |
| 409 | `TASK_ALREADY_FINISHED` | you tried to cancel a task that already succeeded or failed | nothing to cancel: read the task for its result or error |
| 400 | `INVALID_PAGE_TOKEN` | the `page_token` wasn't one we issued | start again from the first page |
| 422 | `INVALID_REQUEST_BODY` | the body is wrong: `input` missing, empty, over 10,000 characters, or an extra field sent | fix the body; `message` names the field |
| 422 | `INVALID_QUERY_PARAMETER` | for example `page_size` outside 1 to 100 | fix the parameter |
| 422 | `INVALID_HEADER` | `Idempotency-Key` is empty or longer than 255 characters | send a key of 1 to 255 characters |
| 422 | `IDEMPOTENCY_KEY_REUSED` | the same idempotency key was used with a different body | use a new key for the new request |
| 500 | `INTERNAL_ERROR` | something went wrong on our side | retry later; if it keeps happening, report it |
| 501 | `NOT_IMPLEMENTED` | the route exists but isn't built yet (the events stream, in v1) | poll `GET /v1/tasks/{id}` instead |

**Safe to retry automatically:** get, list and cancel, after any network failure or a 500. **Create** is safe to retry only with an `Idempotency-Key`.

## Limits

| Limit | Value |
| --- | --- |
| `input` length | 1 to 10,000 characters |
| `page_size` | 1 to 100, default 20 |
| Idempotency keys remembered for | 24 hours |
| Rate limits | none yet in v1 |

## Versioning

The version is in the path: `/v1/`.

**We may add these without notice, so your code should ignore anything it doesn't recognise:**
- new optional fields in responses
- new event types, once the events stream exists

**These would need a new version, `/v2`:**
- removing or renaming a field
- adding a new task state (code that stops polling at a final state could otherwise wait forever)
- changing a `reason` string

## Not in v1 yet

- **Live updates:** `GET /v1/tasks/{id}/events` returns 501 for now, so poll `GET /v1/tasks/{id}` instead.
- **Replying to a task that's `waiting_for_input`.**
- **Webhooks** when a task finishes.

---

## Notes on the week

- **Built:**
  - the five routes, in-memory storage, API-key auth with two scopes, idempotent create and cursor paging
  - then a refactor into four layers (domain, repository, services, API), with the behaviour unchanged
  - 167 tests, pyright strict with 0 errors, and `openapi.json` committed
- **Hardest:** off-by-one bugs in paging (the next token must come from the last task *returned*, not the extra one fetched to check for more), and default arguments that are worked out once at import time (`new_id = "t_" + …`).
- **What I'd do differently:** write the design document's state table and error table before any code, as I did, but also write the tests for pagination edge cases (an exact multiple of the page size, equal timestamps) before the route.
- **Carry into week 5:** a Postgres repository must pass the same 12 repository tests, and the index for `list_tasks` comes straight from this week's query: `(tenant_id, created_at)`, plus `id` for the tie-breaker.