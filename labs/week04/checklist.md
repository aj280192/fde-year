Your `models.py` is correct. `errors.py` has a few bugs, explained below. Before writing the step-by-step for the rest, I'll build the whole thing myself and run it under pyright strict, so the steps warn you about real pitfalls rather than guessed ones. I won't send you that code.

I built the whole of tonight's work myself first, as a reference implementation, and ran it: pyright strict reports 0 errors and 5 test groups pass. The pitfalls I hit are flagged with ⚠️ in the steps below. I'm not sending you that code, so you still write it yourself.

## Your `models.py`: correct ✅

It matches the design exactly: all 6 states, the 10 legal moves, empty sets for the terminal states, and the right model shapes. One addition I'd make:

- **Make `Task` frozen** with `model_config = ConfigDict(frozen=True)`. Code then can't write `task.state = ...` by mistake; it has to make a new copy with `task.model_copy(update={...})`. That's what your cancel step needs.

## Your `errors.py`: four bugs

1. **`task_already_finished` returns the wrong error.** It's a copy of `task_not_found`. It should use **409**, `FAILED_PRECONDITION` and `TASK_ALREADY_FINISHED`.
2. **The f-string prints `'state.name'` as literal text.** It's inside the string's quotes without braces. Write `{state.value}`, which gives `"succeeded"`.
3. **The handler builds `ErrorResponse` with the wrong shape.** `ErrorResponse` has one field, `error`, which holds an `ErrorBody`, which in turn holds a list of `ErrorDetail`s. You have to build it from the inside out:
   ```text
   ErrorResponse(error=ErrorBody(code=exc.http, status=exc.status, message=exc.message,
                                 details=[ErrorDetail(reason=exc.reason)]))
   ```
4. **`.model.dump()` should be `.model_dump()`.** Also add `-> None` to `__init__`, and rename the unused `request` parameter to `_`. Pyright strict flags both.

---

# Tonight and Friday: every step

The whole job is about **4½ hours**. It's 9 pm, so **do steps 1 to 6 tonight** (about 2¼ hours). That gives you working routes, authentication and tests. **Steps 7 to 11 go on Friday** (about 2 hours), plus *AI Engineering* ch. 4. Run `uv run pyright labs/week04` after every step, not just at the end.

## Step 1 · Small changes to `models.py` (5 min)

- Make `Task` frozen, as above. Nothing else changes.

## Step 2 · Fix and finish `errors.py` (15 min)

1. **Fix the four bugs above.**
2. **Add the remaining helpers.** There should be one per `reason` in DESIGN 8b:

| Helper | HTTP | `status` | `reason` |
| --- | --- | --- | --- |
| `not_implemented(what)` | 501 | `UNIMPLEMENTED` | `NOT_IMPLEMENTED` |
| `task_not_found(task_id)` | 404 | `NOT_FOUND` | `TASK_NOT_FOUND` |
| `task_already_finished(task_id, state)` | 409 | `FAILED_PRECONDITION` | `TASK_ALREADY_FINISHED` |
| `invalid_page_token()` | 400 | `INVALID_ARGUMENT` | `INVALID_PAGE_TOKEN` |
| `api_key_invalid()` | 401 | `UNAUTHENTICATED` | `API_KEY_INVALID` |
| `insufficient_permission(scope)` | 403 | `PERMISSION_DENIED` | `INSUFFICIENT_PERMISSION` |
| `idempotency_key_reused()` | 422 | `INVALID_ARGUMENT` | `IDEMPOTENCY_KEY_REUSED` |

3. **Split the handler in two.** First, a plain function `to_response(http, status, reason, message) -> JSONResponse` that builds the nested model and returns `JSONResponse(status_code=http, content=body.model_dump())`. Then `api_error_handler(_, exc)` simply calls `to_response(...)` with the exception's four fields. Step 9's validation handler reuses `to_response`.

**Check:** in a Python shell, `to_response(404, "NOT_FOUND", "TASK_NOT_FOUND", "x").body` shows the nested JSON.

## Step 3 · `auth.py` (15 min)

Write these in order:

1. **Two constants:** `READ = "tasks:read"` and `WRITE = "tasks:write"`.
2. **`Principal`:** a frozen Pydantic model with `key_id: str` and `scopes: frozenset[str]`.
3. **`hash_key(raw: str) -> str`:** SHA-256 of the key as a hex string.
4. **`new_key() -> str`:** `"sk_" + secrets.token_urlsafe(32)`.
5. **A `if __name__ == "__main__":` block** that makes a new key and prints both the key and its hash.

**Check:** run `uv run python labs/week04/auth.py`. Keep the printed key somewhere private, such as a password manager or `.env`; you'll paste it into `/docs` later. Only the **hash** ever goes into code.

## Step 4 · The `api.py` skeleton: factory, stores, handlers, auth (30 min)

There are no routes yet. Build the frame in this order:

1. **`utc_now() -> datetime`**, returning `datetime.now(UTC)`.
2. **`err(*codes) -> dict[int | str, dict[str, object]]`.** It returns `{code: {"model": ErrorResponse}}` for each code you pass. Every route uses it in `responses=`, so `/docs` shows the error shapes.
3. **`create_app(api_keys: Mapping[str, Principal], now: Callable[[], datetime] = utc_now) -> FastAPI`.** Inside it:
   1. **Three stores:**
      - `tasks: dict[str, Task]`
      - `owners: dict[str, str]`
      - `idem: dict[tuple[str, str], IdempotencyRecord]` (add this one in step 8)
   2. **`app = FastAPI(title="Agent task API", version="0.1.0")`.**
   3. **Register the error handler.** ⚠️ `app.add_exception_handler(ApiError, api_error_handler)` **fails pyright strict**: it expects a handler that takes any `Exception`. Use this form instead, which passes:
      ```text
      app.exception_handler(ApiError)(api_error_handler)
      ```
   4. **`key_header = APIKeyHeader(name="X-API-Key", auto_error=False)`.** With `auto_error=False`, a missing header comes through as `None` instead of FastAPI's own 403, so you can return **401** in your own shape.
   5. **`async def principal(raw: Annotated[str | None, Security(key_header)]) -> Principal`.** If `raw` is `None`, or `hash_key(raw)` isn't in `api_keys`, raise `api_key_invalid()`. Otherwise return the matching `Principal`. Using `Security(...)` is what adds the **Authorize** button to `/docs`.
   6. **`def require(scope: str) -> Callable[[Principal], Awaitable[Principal]]`.** It defines and returns an inner `async def check(p: Annotated[Principal, Depends(principal)]) -> Principal`. That inner function raises `insufficient_permission(scope)` if the scope is missing, and otherwise returns `p`.
   7. **`def owned(task_id: str, p: Principal) -> Task`.** If the task is missing, **or** `owners[task_id] != p.key_id`, raise `task_not_found(task_id)`. Get, cancel and events all use it.
   8. **`app.state.tasks = tasks`, then `return app`.** Putting the store on `app.state` lets a test put a `succeeded` task into it. No route can produce a succeeded task yet, because there's no worker.

⚠️ **Don't write `Writer = Annotated[Principal, Depends(require(WRITE))]` inside `create_app`.** Pyright treats it as an ordinary variable and refuses to use it as a type. Write the full `Annotated[...]` in each route's parameter list instead.

## Step 5 · The routes: create, get, cancel, events (30 min)

Put each one inside `create_app`, after the auth functions. List is in step 7.

**Create:** `@app.post("/v1/tasks", status_code=202, responses=err(401, 403, 422))`
- Parameters: `body: CreateTaskRequest` and `p: Annotated[Principal, Depends(require(WRITE))]`. The idempotency parameters come in step 8.
- Steps:
  1. `stamp = now()`.
  2. Build the `Task`: `id="t_" + secrets.token_urlsafe(16)`, `state=QUEUED`, `input=body.input`, and both times set to `stamp`.
  3. Store it in `tasks`, and record `owners[task.id] = p.key_id`. Return the task.
- Add a one-line docstring, as for every route; `/docs` shows it.

**Get:** `@app.get("/v1/tasks/{task_id}", responses=err(401, 403, 404))`
- Takes `p` with `READ`, and returns `owned(task_id, p)`.

**Cancel:** `@app.post("/v1/tasks/{task_id}:cancel", responses=err(401, 403, 404, 409))`
- Takes `p` with `WRITE`. Then, in this order:
  1. `task = owned(task_id, p)`. That gives a 404 if the task is missing or someone else's.
  2. If `task.state is TaskState.CANCELLED`, return the task unchanged. This makes cancel idempotent.
  3. If the state is in `TERMINAL`, or `can_transition(task.state, CANCELLED)` is false, raise `task_already_finished(task_id, task.state)`.
  4. `updated = task.model_copy(update={"state": TaskState.CANCELLED, "updated_at": now()})`, save it in `tasks`, and return it.
- Add a code comment above step 1: *"No `await` between the check and the write, so two cancels can't interleave in asyncio. With a database this must become one conditional update (Saturday)."*

**Events:** `@app.get("/v1/tasks/{task_id}/events", responses=err(401, 403, 404, 501))`
- Takes `p` with `READ`, and returns `-> None`.
- Call `owned(task_id, p)` first, so an unknown id still gets a 404. Then raise `not_implemented("The events stream")`.

## Step 6 · First tests: `test_api.py` (30 min)

### The setup

1. **`KEYS`:** a dict of three raw test keys, `{"alice": "sk_alice", "bob": "sk_bob", "reader": "sk_reader"}`. Simple strings are fine in tests.
2. **`FakeClock`:**
   - It starts at a fixed UTC time.
   - It has a `now()` method.
   - It has an `advance(**kw)` method, which adds `timedelta(**kw)`.
   - Make a `clock` fixture that returns one.
3. **A `client` fixture,** depending on `clock`. It builds a `{hash_key(raw): Principal(...)}` dict:
   - alice and bob have `{READ, WRITE}`
   - reader has `{READ}`
   - then return `TestClient(create_app(keys, now=clock.now))`
4. **Two helpers:**
   - `h(who, **extra)` returns `{"X-API-Key": KEYS[who], **extra}`
   - `reason(response)` returns `response.json()["error"]["details"][0]["reason"]`

`TestClient` runs the app in-process, so unlike week 3 you don't need a uvicorn thread.

### Tests for tonight

| Test | Steps | Expect |
| --- | --- | --- |
| Create, then get | alice creates, then gets | 202; then 200, the same id, `queued` |
| Unknown id | get `/v1/tasks/nope` | 404, `TASK_NOT_FOUND` |
| Cancel twice | alice cancels, then cancels again | both 200, `cancelled`, **identical** bodies (same `updated_at`) |
| Cancel a finished task | put a `succeeded` copy into `client.app.state.tasks`, then cancel | 409, `TASK_ALREADY_FINISHED` |
| No key | `GET /v1/tasks` with no header | 401, `API_KEY_INVALID` |
| Wrong key | header `sk_wrong` | 401 |
| Read-only key creates | reader posts | 403, `INSUFFICIENT_PERMISSION` |
| Read-only key reads | reader gets an unknown id | 404, not 403 (their scope allows reading) |
| Someone else's task | alice creates, then bob gets it | **404** |
| Someone else's cancel | bob cancels alice's task | **404**, and alice's task is still `queued` |

**Tonight is done** when `uv run pytest labs/week04 -v` and `uv run pyright labs/week04` both pass. Commit with `week04: task routes with in-memory store and API-key auth`.

---

## Step 7 · Pagination (Friday, 45 min): `pagination.py`, the list route, tests

**`pagination.py`:**
- `encode_cursor(created_at: datetime, task_id: str) -> str`: `json.dumps({"t": created_at.isoformat(), "id": task_id})`, then `.encode()`, then `base64.urlsafe_b64encode`, then `.decode()`.
- `decode_cursor(token: str) -> tuple[datetime, str]`: the reverse, inside `try`. On `ValueError`, `binascii.Error`, `KeyError` or `TypeError`, `raise invalid_page_token() from exc`. Never use a bare `except`.

**List route:** `@app.get("/v1/tasks", responses=err(400, 401, 403, 422))`
- Parameters:
  - `p` with `READ`
  - `page_size: Annotated[int, Query(ge=1, le=100)] = 20`
  - `page_token: str = ""`
- Steps:
  1. **The caller's tasks only:** keep the tasks where `owners[t.id] == p.key_id`.
  2. **Sort** by the key `(t.created_at, t.id)`, with `reverse=True`, so the newest come first.
  3. **If there's a token,** decode it and keep only the tasks where `(t.created_at, t.id) < cursor`. Python compares tuples one position at a time, which is exactly the rule you want.
  4. **Take one extra:** `page = mine[: page_size + 1]`. If you got more than `page_size`, cut it back to `page_size` and set `next_page_token` to `encode_cursor` of the **last item kept**. Otherwise, return with the default empty token.

**Tests:**

| Test | Steps | Expect |
| --- | --- | --- |
| Pages | create 5 tasks, with `clock.advance(seconds=1)` between them, then list with `page_size=2` | page sizes 2, 2, 1; the last token is `""` |
| Walk every page | loop until the token is empty | all 5 ids, each exactly once |
| Tie-breaker | skip `advance` between two of the creates, so they share a timestamp | both still appear, once each |
| New task while paging | create a task after reading page 1 | the original 5 are still seen once each, with no duplicates. This is the point of cursors |
| Bad token | `page_token="garbage"` | 400, `INVALID_PAGE_TOKEN` |
| Isolation | bob lists | none of alice's tasks |

## Step 8 · Idempotency (Friday, 40 min): `idempotency.py`, create, tests

**`idempotency.py`:**
- `TTL = timedelta(hours=24)`.
- `IdempotencyRecord`: `fingerprint: str`, `task_id: str`, `created_at: datetime`.
- `fingerprint(body: CreateTaskRequest) -> str`: SHA-256 of `json.dumps(body.model_dump(), sort_keys=True)`. Fingerprinting the parsed model means differences in spacing don't count as a different body.

**Changes to the create route:**
- Add two parameters:
  - `response: Response`, so you can set a header
  - `idempotency_key: Annotated[str | None, Header(min_length=1, max_length=255)] = None`

  ⚠️ FastAPI turns the underscore into a hyphen automatically, so the header clients send is `Idempotency-Key`.
- **At the start of the route,** if a key was sent:
  1. Look up `idem.get((p.key_id, idempotency_key))`. The `key_id` is part of the dict key, so two clients that use the same idempotency key never collide.
  2. If a record exists **and** `now() - record.created_at <= TTL`:
     - if its fingerprint is **different** from this body's, raise `idempotency_key_reused()`
     - if it's the same, set `response.headers["Idempotent-Replayed"] = "true"` and return `tasks[record.task_id]`, **without creating anything**
- **At the end, after creating a task,** if a key was sent, store an `IdempotencyRecord` for it.
- Note in DESIGN section 11 that a replay returns the task **as it is now**, not a copy of the original response.

**Tests:**

| Test | Expect |
| --- | --- |
| Same key and same body, twice | the same id, 202 both times, an `Idempotent-Replayed: true` header, and only 1 task stored |
| Same key, different body | 422, `IDEMPOTENCY_KEY_REUSED` |
| alice and bob send the same key | two **different** task ids |
| Same key after `clock.advance(hours=25)` | a new task id |
| No header, sent twice | 2 tasks |

## Step 9 · Validation errors in your shape, `serve.py`, `/docs` and `openapi.json` (Friday, 25 min)

1. **A `RequestValidationError` handler,** inside `create_app`, registered with the decorator `@app.exception_handler(RequestValidationError)`:
   - Take `first = exc.errors()[0]`. Its `loc` is a tuple such as `("body", "input")` or `("query", "page_size")`.
   - If `loc[0]` is `"body"`, use `INVALID_REQUEST_BODY`. Otherwise use `INVALID_QUERY_PARAMETER`.
   - Make the message from the field path and `first["msg"]`, then `return to_response(422, "INVALID_ARGUMENT", reason, message)`. **Never include the submitted input**, which could be 10,000 characters.
   - **Tests:** creating with an extra `state` field gives `INVALID_REQUEST_BODY`, and `page_size=101` gives `INVALID_QUERY_PARAMETER`. Both come back in your shape.
2. **`serve.py`:** build `app = create_app({"<your key's hash>": Principal(key_id="me", scopes=frozenset({READ, WRITE}))})`, then `uvicorn.run(app, port=8000)` inside `if __name__ == "__main__":`.
3. **Run it** with `uv run python labs/week04/serve.py`, open `localhost:8000/docs`, and tick each of these:
   - [ ] The **Authorize** button: paste your key, and calls work. Without it, calls get 401 in your shape.
   - [ ] Create shows the optional `idempotency-key` header and a **202** response.
   - [ ] List shows `page_size` (between 1 and 100) and `page_token`.
   - [ ] Each route lists its error codes, using `ErrorResponse`.
   - [ ] Each route shows its docstring.
4. **Commit the contract:**
   ```bash
   cd labs/week04
   uv run python -c "import json; from serve import app; print(json.dumps(app.openapi(), indent=2))" > openapi.json
   cd ../..
   ```
   From now on, any change to the API shows up as a diff of this file in review.

## Step 10 · `test_models.py`, Wednesday's step 6 (Friday, 10 min)

| Test | Expect |
| --- | --- |
| Every state has rules | every `TaskState` is a key in `ALLOWED` |
| Legal moves are allowed | parametrized over all 10 legal pairs: `can_transition` gives `True` |
| Illegal moves are refused | a selection: `queued` to `succeeded`, `waiting_for_input` to `succeeded`, any move out of the three terminal states, and `running` to `running` |
| Terminal states have no exits | for every state in `TERMINAL`, `ALLOWED[state]` is empty |

## Step 11 · Update `DESIGN.md` and commit (Friday, 15 min)

1. **Sections 9 to 11:** replace the placeholders with what you actually built:
   - **9:** the cursor contents, newest-first order, the `page_size + 1` trick, and a bad token giving 400. Note that the token is base64 and not signed.
   - **10:** the `X-API-Key` header, SHA-256 hashes, the two scopes, and someone else's task giving 404.
   - **11:** the store is keyed by `(key_id, idempotency key)`, uses a body fingerprint, lasts 24 hours, and a replay returns the task as it is now.
2. **Section 14, three new rows:**
   - the events route returns 501 until there's a worker
   - page tokens aren't signed with an HMAC, so a client could edit one
   - a real database needs a unique constraint on `(key_id, idempotency_key)`
3. **Final checks and commit:**
   ```bash
   uv run pytest labs/week04 -v && uv run pyright labs/week04
   uv run ruff check labs/week04 && uv run ruff format labs/week04
   git add labs/week04 && git commit -m "week04: cursor pagination, idempotent create, openapi.json" && git push
   ```

---

## The schedule

| When | Steps | Time |
| --- | --- | --- |
| **Thu, tonight** | 1 to 6: models, errors, auth, the API skeleton, routes, first tests | about 2¼ h |
| **Fri** | 7 to 11: pagination, idempotency, the docs check, `openapi.json`, model tests, `DESIGN.md` | about 2 h |
| **Fri** | *AI Engineering* ch. 4 | about 1 h, or Sunday morning if Friday runs late |
| **Sat** | *Architecture Patterns* ch. 1 to 4, and the refactor into layers | unchanged |

Paste `errors.py` once it's fixed, then `api.py` after step 5, and I'll check each before you build on it.