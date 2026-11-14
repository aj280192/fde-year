# Week 6 · TypeScript, the language

Python to TypeScript, under `strict` from the first file. The TypeScript Handbook typed out by hand, the
week 2 tool models rebuilt in Zod, and (Thursday) a typed client for the week 4 task API.

| File | What it covers |
| --- | --- |
| `01-basics.ts` … `09-utility-types.ts` | the TypeScript Handbook, typed out under `strict`; each deliberate error left as a comment with its message |
| `zod-tools.ts` | the week 2 tool models (`ToolSpec`, `ToolCall`, `ToolResult`) as Zod schemas; every type derived with `z.infer` |
| `payloads.ts` | the six invalid payloads from week 2, shared by the script and the tests |
| `zod-payloads.ts` | runs the payloads through Zod and prints every issue |
| `zod-payloads.test.ts` | the same, as tests |

```bash
npm install
npm run check      # type-check everything, under strict
npm test           # run every *.test.ts
npx tsx zod-payloads.ts
```

## The setup

`tsconfig.json` turns on `strict`, plus three checks it doesn't include:

| Setting | Effect |
| --- | --- |
| `noUncheckedIndexedAccess` | `arr[0]` is `T \| undefined`, so it must be checked before use |
| `exactOptionalPropertyTypes` | an optional property may be absent, but can't be set to `undefined` |
| `verbatimModuleSyntax` | type-only imports must say `import type` |

`tsx` runs a file **without checking its types**; `tsc --noEmit` (`npm run check`) checks them and runs
nothing. Types are erased at runtime, so data from outside is checked with Zod.

## Zod against Pydantic: the same six invalid payloads

The six payloads from `labs/week02/toolkit/tests/test_models.py`, through the week 2 Pydantic models and
through Zod 4. Both columns are real output.

| # | Payload | Pydantic (week 2) | Zod 4 |
| --- | --- | --- | --- |
| 1 | `ToolCall` with no `name` | `name` · `missing` · "Field required" | `name` · `invalid_type` · "expected string, received undefined" |
| 2 | `arguments` is a string | `arguments` · `dict_type` · "Input should be an object" | `arguments` · `invalid_type` · "expected record, received string" |
| 3 | an extra field | `extra_field` · `extra_forbidden` | the object itself (`[]`) · `unrecognized_keys`, with `keys: ["extra_field"]` |
| 4 | `kind: "done"` | `outcome` · `union_tag_invalid` · "does not match any of the expected tags: 'success', 'error'" | `outcome.kind` · `invalid_union` · "Invalid discriminator value. Expected 'success' \| 'error'" |
| 5 | an error with `content` and no `message` | **two errors:** `outcome.error.content` · `extra_forbidden`, and `outcome.error.message` · `missing` | **two errors:** `outcome` · `unrecognized_keys` (`content`), and `outcome.message` · `invalid_type` |
| 6 | `name` is a number | `name` · `string_type` · "Input should be a valid string" | `name` · `invalid_type` · "expected string, received number" |

**What I noticed:**

- **Both rejected all six, for the same reasons.** The differences are in how they report it, not in
  what they catch.
- **Pydantic's error codes are more specific.** It has a code for each problem (`missing`, `dict_type`,
  `string_type`), so code can react to the exact problem. Zod uses one broad `invalid_type` for three of
  them and puts the detail ("expected string, received undefined") in the message, which is easier to
  read but harder to branch on.
- **Extra keys are reported in different places.** Pydantic puts the bad key in the path
  (`extra_field`). Zod points at the object that has it (`[]`, or `outcome`) and lists the keys in a
  separate `keys` field. Pydantic's form is easier to show next to a form field; Zod's groups several
  extra keys into one issue.
- **Pydantic names the union variant in the path; Zod doesn't.** Pydantic says
  `outcome.error.content`, so you can see which variant it checked against. Zod says `outcome.message`.
- **Payload 5 has two problems, and both libraries report both.** My week 2 test only asserted on
  `errors()[0]`, so it never showed the missing `message`. A test should check every error, not just
  the first: the week 6 tests compare the full, sorted list.
- **A discriminated union fails on the tag first, in both.** With `kind: "done"`, neither library
  reports the fields of every variant; both say the tag is wrong and list the allowed values. That's
  the reason to use a discriminated union rather than a plain union.
- **One structural difference.** In Pydantic, one class is both the runtime check and the type. In
  TypeScript the types don't exist at runtime, so Zod splits them: the schema is a value that checks
  data, and `z.infer<typeof Schema>` derives the type from it. Writing the type by hand as well would
  let the two drift apart, so I don't.
- **Defaults to remember.** Zod's plain `z.object` silently **drops** unknown keys (like Pydantic's
  default `extra="ignore"`); `z.strictObject` rejects them (`extra="forbid"`). And Zod never converts
  `"5"` to `5` unless asked (`z.coerce`), which matches Pydantic's `strict=True`.
## A typed client for the task API (Thursday)

A small TypeScript client for the week 4 and 5 task API. Requests are typed from the API's own OpenAPI
spec, every response is checked with Zod before it's used, errors arrive as `ApiError` with the API's
stable `reason`, and server-sent events are read as an async generator the caller can cancel.

| File | Does |
| --- | --- |
| `src/api.d.ts` | types generated from `labs/week05/openapi.json` with openapi-typescript (don't edit; regenerate) |
| `src/schemas.ts` | Zod schemas for the responses; a compile-time check fails if they ever differ from the generated types |
| `src/client.ts` | `createTask`, `getTask`, `listTasks`; every failure as an `ApiError(status, reason, message)` |
| `src/sse.ts` | `parseSse`: complete events from a byte stream, across chunk boundaries |
| `src/stream.ts` | `streamEvents` (any SSE URL) and `streamTaskEvents`, both cancellable with an `AbortSignal` |
| `src/sse.test.ts` | the parser: an event split across chunks, a character split across chunks, several data lines, an early `break` |
| `src/demo.ts` | the client against the real week 4 server |
| `src/ask-demo.ts` | `streamEvents` against week 3's real `/ask` stream, then an abort |

```bash
npx openapi-typescript ../week05/openapi.json -o src/api.d.ts     # after any API change

# against the task API (week 4, in memory)
uv run python ../week04/api/auth.py                                # prints a key and its hash
TASKS_API_KEY_HASH=<hash> uv run python ../week04/serve.py
TASKS_API_KEY=<key> npx tsx src/demo.ts

# against week 3's stream (stop the week 4 server first: both use port 8000)
(cd ../week03 && uv run uvicorn fake_upstream:app --port 9000)
(cd ../week03 && LLM_BASE_URL=http://127.0.0.1:9000/v1 uv run python serve.py)
npx tsx src/ask-demo.ts
```

**What the demos show** (12 and 14 Nov, against the real servers):

| Call | Result |
| --- | --- |
| create twice with the same `Idempotency-Key` | the same task id both times |
| list with `pageSize: 1`, then the `next_page_token` | one task per page, newest first |
| get `t_missing` | `ApiError 404 TASK_NOT_FOUND` |
| stream a task's events | `ApiError 501 NOT_IMPLEMENTED` (no worker yet) |
| stream week 3's `/ask` | 13 events: the answer's tokens, then `done` with token usage |
| abort after the first event | the loop stops with `AbortError`, and the connection is closed |

**Decisions:**

- **Every response is `unknown` until Zod checks it.** `res.json()` returns `any`; assigning it to
  `unknown` keeps that `any` out of the code. There is no `any` in the client's files.
- **Response schemas use `z.object`, not `z.strictObject`.** They ignore fields they don't know, so the
  client keeps working when the server adds an optional field, which the week 4 guide says it may.
- **`result` and `error` use `.exactOptional()`.** Under `exactOptionalPropertyTypes`, the generated
  `result?: string | null` excludes `undefined`; `.optional()` would add it, and the compile-time check
  against the spec would fail.
- **The parser keeps the unfinished end of the buffer.** A chunk can end in the middle of an event, or
  of a character; only text followed by a blank line is parsed, and the decoder runs with
  `stream: true`.
- **Cleanup is in `finally`.** Whether the stream ends, the caller breaks out early, or it's aborted, the
  reader is cancelled and the connection closes (tested).

**Harder than in Python:**

- **Reading SSE by hand.** In Python I had a library; here the byte stream, the buffering across chunks
  and the line endings are my code, and each of those was a test.
- **Nothing is checked unless I check it.** Types vanish at runtime, so every response needs a runtime
  check as well as a type. Pydantic gives both from one class; here the Zod schema and the generated
  type are separate, and a compile-time check keeps them in step.
- **Optional is stricter than `None`.** Under `exactOptionalPropertyTypes`, an optional property can be
  missing but not `undefined`, so options such as `signal` are added only when given, never set to
  `undefined`.
