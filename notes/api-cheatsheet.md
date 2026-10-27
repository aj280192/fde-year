# API design cheat sheet (Google AIPs)

Read on Tue 27 Oct 2026 from Google's API Improvement Proposals ([google.aip.dev](https://google.aip.dev/)). Used in Wednesday's task API design and Thursday's idempotency, pagination and auth work.

## Resources are nouns ([AIP-121](https://google.aip.dev/121))

- **Rule:** the URL path names resources, as plural nouns (`/v1/tasks`, `/v1/shelves/{shelf}/books`). No verbs in the path: the action comes from the HTTP method, or from a custom method on the end (`:cancel`).
- **Why:** the API becomes a predictable tree of things, with a small set of verbs that work the same everywhere. A client who knows how to `List` one resource knows how to `List` all of them. With verbs in paths (`/runTask`, `/getTaskStatus`), every endpoint is a one-off, and the URLs sprawl.
- **In my task API:** the resources are `tasks` and a task's `events`. Cancelling is an action, so it's a custom method, `POST /v1/tasks/{id}:cancel`, not a resource.

## Resource names ([AIP-122](https://google.aip.dev/122))

- **Rule:** every resource has one unique name that is its path: `tasks/{task_id}`, and for a child, `tasks/{task_id}/events/{event_id}`. Collection names are plural, and the name never changes once the resource exists.
- **Who picks the id:** usually the server. That's what I'll do: the server generates the task id, so two clients can never clash.
- **Why:** the name is enough to find the resource, so clients store and pass names, not database ids.

## The five standard methods ([AIP-131](https://google.aip.dev/131) to [AIP-135](https://google.aip.dev/135))

| Method | HTTP | Returns | Status code |
| --- | --- | --- | --- |
| Get | `GET /v1/tasks/{id}` | The resource itself | 200 OK |
| List | `GET /v1/tasks` | A wrapper: the list of resources and a `next_page_token` | 200 OK |
| Create | `POST /v1/tasks` | The newly created resource | 200 OK in Google's APIs; 201 Created is the common REST convention |
| Update | `PATCH /v1/tasks/{id}` | The updated resource | 200 OK |
| Delete | `DELETE /v1/tasks/{id}` | Empty | 200 OK, or 204 No Content in plain REST |

- **Update uses `PATCH`,** with a field mask saying which fields to change. AIP-134 discourages `PUT`, because a full replace silently wipes any field the client didn't send, including fields added in later versions.
- **Every method except List returns the resource itself,** so a client never needs a second call to see what it just created or changed.
- **Custom methods ([AIP-136](https://google.aip.dev/136))** are for actions that don't fit the five: `POST /v1/tasks/{id}:cancel`. Always `POST`, with a colon before the verb. Use them sparingly; if a standard method fits, use that.

## One error shape ([AIP-193](https://google.aip.dev/193))

- **Fields:**
  - `code`: the status code
  - `message`: for the **developer** reading logs, not for end users
  - `status`: the canonical name, such as `NOT_FOUND` or `INVALID_ARGUMENT`
  - `details`: structured extras. The important one is an `ErrorInfo` with a machine-readable `reason` (such as `TASK_ALREADY_FINISHED`) and a `domain`.
- **Why one shape for every error:** a client writes its error handling once, and it works for every route. Clients branch on `reason` and `code`, never on the wording of `message`, so I can improve the wording without breaking anyone. Without a standard shape, each endpoint fails differently, and every client needs custom code per endpoint.
- **In my task API:** one Pydantic `ErrorResponse` model used by every route, including 401, 403, 404, 409 and 422. My week 3 `/ask` already had the same idea: a stable `code` for machines, and a safe `message`.

## Pagination: page tokens, not page numbers ([AIP-158](https://google.aip.dev/158))

- **How it works:** the client sends `page_size` and, after the first page, a `page_token`. The server returns one page of results plus a `next_page_token`. The client passes that token back unchanged to get the next page, and stops when `next_page_token` comes back empty.
- **Rules to remember:**
  - The token is **opaque**. Clients must not parse it or build their own, so the server can change what's inside it.
  - The server may return fewer items than `page_size`, and may cap it. A short page doesn't mean the end; only an empty `next_page_token` does.
  - If the client changes the filters between pages, reject the token.
- **Why page numbers break:** they assume the data stands still while someone pages through it.
  - **Duplicates and skips:** if a new task is created, or one is deleted, while a user moves from page 1 to page 2, every item shifts position. With page numbers, the user then sees one task twice or misses one entirely, and nothing tells them.
  - **Slow deep pages:** `OFFSET 10000` makes the database read and throw away 10,000 rows before returning the next page. A token works like a cursor: it pins the last item seen (creation time plus id), so the query starts straight after it using an index.
- **In my task API (Thursday):** the token encodes the last task's `created_at` and `id`. I include the `id` because two tasks can share a timestamp, and the id breaks the tie so the order is total.

## Two things I'll use this week

- **Long-running work ([AIP-151](https://google.aip.dev/151)):** when work takes longer than a request should wait, return straight away with something the client can poll, instead of holding the connection open. That's why `POST /v1/tasks` returns **202 Accepted** with the task in `queued` state. The client then polls `GET /v1/tasks/{id}`, or streams `/events`.
- **Retrying a create safely ([AIP-155](https://google.aip.dev/155)):** the client sends a unique request id with a create. If the network drops and it retries, the server recognises the id and returns the first result instead of creating a duplicate. Thursday's `Idempotency-Key` header is the same idea: same key and same body gives the stored response, and same key with a different body is rejected.