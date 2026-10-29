## Tue 20 and Wed 21 Oct · Fluent Python ch. 19 to 21, asyncio

### What I understood

1. **await and gather.** A for loop that awaits each fetch runs them one after another, so three 1-second fetches take 3 seconds. `gather` starts them all and waits for all of them, so they take about 1 second. Everything runs on one thread: each task runs until it hits an `await`, then another continues. It feels parallel because the waiting overlaps, and an LLM call is almost all waiting. Results come back in the order I passed them in.
2. **Semaphore.** Limits how many run at once. `gather` still starts all 20 tasks; the limit is the `async with limit` inside `fetch`, where only N tasks hold a ticket and the rest wait at that line. It protects whatever is inside the block, such as the call to the model.
3. **Two different protections.** `asyncio.timeout` stops a call that hangs. `return_exceptions=True` stops one failure from throwing away the other results, but it does not handle errors for me: failures come back as items in the list, and I have to check each one.
4. **Cancellation.** `task.cancel()` makes asyncio raise `CancelledError` inside the task, at the `await` where it is paused. My code cleans up and re-raises it, so the task ends as "cancelled", not "finished".

### Where cancellation comes from in a real system

- The user closes the tab or clicks Stop while an answer streams: the server notices the disconnect, cancels the model call, the HTTP connection closes, and the provider stops generating, so I stop paying for tokens. I build this on Saturday.
- The user cancels a long-running job through a cancel route in the task API.
- A time budget runs out: `asyncio.timeout` is cancellation underneath, turned into a `TimeoutError`.

### Cheat sheet

| Use | When |
| --- | --- |
| `asyncio.gather(..., return_exceptions=True)` | Run many calls together and keep every result, including failures |
| `asyncio.TaskGroup` | Run many calls together when all must succeed: the first failure cancels the rest |
| `asyncio.Semaphore(n)` | At most n calls in flight, to avoid rate limits or overloading a server |
| `asyncio.timeout(seconds)` | Give up on a call that hangs |
| `asyncio.create_task` and `task.cancel()` | Start work in the background, and stop it when nobody needs it |
| `asyncio.to_thread` | Run blocking code, such as a library without async support, without freezing the others |

- **At an `await`:** this task pauses and the event loop runs another until the awaited thing is ready.
- **Never swallow `CancelledError`:** if I catch it, clean up and re-raise. Otherwise the task looks finished, and the connection to the model may stay open.
- **Order matters:** my cancellation handler sits outside the `asyncio.timeout` block, or it would also fire on every timeout.

### My script's result

- [14] succeeded, [6] failed: [TimeoutError]
- Peak in flight: [5]
- Total time: [5.1] seconds, against about 20 one after another
- Extra task cancelled: [True]

### Question

[One thing still unclear, for example: what happens to a task's semaphore ticket when it is cancelled while waiting for one?]

## Thu 22 Oct · Async LLM client

Built `LLMClient` with `complete()` and `stream()` against any OpenAI-compatible endpoint, a fake model server that streams a canned answer word by word, and three tests. Ran it against both the fake server and Ollama ([model name]): the same client works for both by changing the URL.

### Four decisions

1. **One shared client.** Opening an HTTP connection is costly, so I create one `httpx.AsyncClient` and reuse it for every call instead of paying that cost each time.
2. **A timeout per stage.** Each stage takes a different time: connecting should take a few seconds, while reading can take much longer. The read timeout is the longest gap between pieces, not the whole answer, so a long streamed answer does not time out while it keeps producing words.
3. **`async with` everywhere.** The context manager always closes the connection, including when the caller stops halfway or is cancelled. The cancellation test proves the server sees the disconnect and stops sending.
4. **Lenient response models.** Providers add fields to their responses over time, so I ignore unknown fields. My code does not break when the format grows, and Pydantic still checks the fields I read. This is the opposite of week 2: strict for untrusted input, lenient for a provider's output.

### What a stream looks like

Server-sent events: one `data: {json}` line per piece, separated by blank lines, ending with `data: [DONE]`. My client reads line by line, skips blank lines, stops at `[DONE]`, and yields each `delta.content`.

### Results

- 3 tests pass: complete, stream in order, and cancelling a stream closes the connection
- Pyright strict: 0 errors

## Fri 23 Oct · AI Engineering ch. 3, evaluation methodology (moved from Monday)

### Five lines

- New: the division of evaluation into reward models, reference-based judges and preference models was partly new to me.
- New: "exact" evaluation means a program computes the score by a fixed rule, not that the output must match word for word. So lexical and embedding similarity count as exact.
- Changes how I would build: use exact checks wherever a right answer exists, and keep the LLM judge for what they cannot measure, such as tone or helpfulness.
- Changes how I would build: for NLP-to-SPL, run the generated query over a fixed time window and compare the records it returns with the reference query's records. That is functional correctness, and comparing records rather than counts avoids accidental matches.
- Question: where is LLM-as-judge not a good evaluation method?

### Exact or judged

| Method | Exact or judged | Needs reference answers? | One weakness |
| --- | --- | --- | --- |
| Functional correctness | Exact | Yes, as test cases or expected results | Cannot be used for open-ended tasks such as a customer chatbot |
| Exact match | Exact | Yes | Misses answers that mean the same thing in different words |
| Lexical similarity | Exact | Yes | Scores semantically similar outputs low when the wording differs |
| Embedding similarity | Exact | Yes | Only as good as the embedding model that produces the vectors |
| AI as a judge | Judged | Optional | Can be biased, and hard to keep consistent |
| Comparative ranking | Judged | No | Shows which model is better, not whether either is good enough |

### My benchmark at work

| Metric | Exact or judged | How I use it |
| --- | --- | --- |
| Semantic similarity | Exact, when computed by a rule | A correct query uses the same set of operations as the reference. For "users who accessed social media", it must filter the URLs, aggregate over users and return the answer. |
| Latency | Exact (measured) | I compare the execution time of the generated query with the reference query's. |
| Valid query | Exact (checked by a validator) | I score whether the generated query is valid, regardless of whether it answers the question. On failure the model retries with the validation error. The benchmark's questions increase in difficulty. |
| LLM as judge | Judged | The judge compares the generated query with the reference. |

One weakness the chapter exposed: nothing in my benchmark checks that the generated query returns the right records. A query can be valid, use similar operations and win the judge's approval, yet answer the wrong question. Running both queries over the same time window and comparing their records would close that gap, which is functional correctness.

# Week 3 · 19–25 October 2026 · Async Python and a resilient LLM client

## What I built

`labs/week03/`: a small gateway in front of any OpenAI-compatible model (Ollama, OpenAI, vLLM).

| File | What it does |
| --- | --- |
| `fake_upstream.py` | A pretend model server with failure modes: `ok`, `server_error`, `rate_limited`, `rate_limited_twice`, `hang`, `drop` |
| `errors.py` | My own errors, each with a `code`: `UpstreamError`, `RateLimitedError`, `UpstreamTimeoutError`, `UpstreamDroppedError` |
| `client.py` | `LLMClient` with `complete()` and `stream()`: retries, full-jitter backoff, `Retry-After`, a total time budget, and a semaphore |
| `app.py` | `POST /ask`: streams the answer as SSE (`token`, `done`, `error`, `: ping`) and stops the model when the user leaves |
| `serve.py` | Runs the app by hand against Ollama or the fake |

35 tests, about 11 seconds, pyright strict with 0 errors.

## Every way an LLM call can fail

| Failure | How it's detected | What the client does | What the user sees | Test that proves it |
| --- | --- | --- | --- | --- |
| Rate limited (429) | `HTTPStatusError` with status 429, so `classify` returns `RateLimitedError` | Retries. Waits `Retry-After` (capped at `max_delay`), or the backoff if there's no header. Gives up after `max_attempts` or the time budget. | Usually the answer, just a little later. If retries run out: `event: error`, code `rate_limited`, "The model is busy. Try again shortly." | `test_retry_recovers_after_two_429s`, `test_gives_up_on_repeated_429`, `test_retry_after_is_capped_at_max_delay`, `test_rate_limited_becomes_one_error_event` |
| Server error (500, 502, 503, 504) | `HTTPStatusError` with a status in `RETRYABLE_STATUS`, so `UpstreamError` | Retries with backoff, then gives up with `UpstreamError` | The answer, or `error` with code `upstream_error`, "The model is unavailable right now." | `test_server_error_retries_then_fails`, `test_error_message_hides_internal_details` |
| Bad request (400, 401, 404, 501) | `HTTPStatusError` with any other status, so `classify` returns `None` | **No retry.** Raises `UpstreamError` straight away: the same request would fail the same way. | `error` with code `upstream_error` on the first try | `test_classify` |
| Can't connect | `httpx.ConnectError`, so `UpstreamError` | Retries with backoff (the server may be restarting), then `UpstreamError` | The answer, or `error` with code `upstream_error` | `test_classify` |
| No answer before the read timeout (`complete`) | `httpx.ReadTimeout` (a `TimeoutException`), so `UpstreamTimeoutError` | Retries with backoff. Safe, because nothing reached the user yet. | The answer, or `error` with code `upstream_timeout`, "The model took too long to answer." | `test_hang_before_anything_arrives_retries` (3 requests) |
| Stalls after the first word (`stream`) | `ReadTimeout` while `yielded` is `True` | **No retry.** Raises `UpstreamTimeoutError` | One token, then `: ping` heartbeats, then `error` with code `upstream_timeout` | `test_stream_hang_after_first_piece` (1 request), `test_hang_sends_heartbeats_then_timeout` |
| Connection cut mid-answer | The server crashing shows up on my side as `httpx.RemoteProtocolError`, while `yielded` is `True` | **No retry.** Raises `UpstreamDroppedError` | The words so far, then `error` with code `upstream_dropped`, "The answer was cut off. Try again." | `test_stream_drop_mid_answer` (1 request), `test_drop_sends_tokens_then_error` |
| Stream ends without `[DONE]` | The `async for` over lines finishes, but we never saw `[DONE]` | Raises `UpstreamDroppedError("stream ended without [DONE]")` instead of pretending the answer is complete | The words so far, then `error` with code `upstream_dropped` | None yet: my fake always sends `[DONE]` |
| The user closes the tab | Starlette cancels the request (and `request.is_disconnected()` is the backup check) | `finally` cancels the producer. The shield lets httpx close the upstream connection, so the model stops generating. | Nothing, they've gone. What matters is that we stop paying for tokens. | `test_browser_leaving_stops_the_model` |
| Too many requests at once | Nothing errors: the semaphore (`max_in_flight`, default 10) simply has no free slot | Extra requests **wait in line** for a slot. That's queuing, not backoff. Retrying requests release their slot while they sleep. | A slower start. Heartbeats keep the connection open while they wait. | None yet: this week's work exercise on vLLM covers it |

Two things to remember about the table:

- `classify` only decides **before** any text has gone out. Once `yielded` is `True`, the cause alone picks the error: a timeout gives `UpstreamTimeoutError`, anything else gives `UpstreamDroppedError`.
- Three different questions have three different answers: an invalid body sent to **my** app gets a 422 from FastAPI before the model is ever called (`test_bad_request_is_rejected_before_calling_the_model`), a bad request to the **model** gets an `error` event, and every stream that starts ends with exactly one `done` or one `error`.

## Three things I learned

**1. Why a stream never retries after the first piece.** A retry starts the answer again from the first word. The user has already seen "Pods restart when", so a retry would show it twice, or start differently, because a model doesn't give the same answer twice and can't resume from the middle. Before the first piece, a retry is invisible to the user, so it's safe. After it, cutting off with a clear error is better than a confusing repeat.

**2. Why the producer and the queue exist.** It's all one process and one thread, so the problem isn't doing two things in parallel. The problem is that `asyncio.wait_for` **cancels the thing it's waiting on** when it times out. If I wait on the stream itself with a 15-second timeout so I can send a heartbeat, the timeout closes the stream, and the answer is gone (`trap_demo.py` printed `[generator closed]` and lost the last words). So the stream runs in its own task, the producer, which only puts pieces into a queue. My loop waits on `queue.get()` instead. A timeout there just cancels "waiting on an empty queue", which is harmless: I send `: ping` and wait again, and the producer never notices.

**3. The disconnect bug, and why the shield fixes it.** When the user closes the tab, my `finally` cancels the producer, and the producer's httpx stream should close the connection to the model. The disconnect test failed: the fake server went on sending all 12 words to nobody. Tracing it showed why. Starlette cancels the request through anyio, and anyio doesn't cancel once: it **keeps re-cancelling** until the work stops. One of those repeat cancellations landed while httpx was in the middle of closing the connection, so the close was interrupted and the connection to the model stayed open. `with anyio.CancelScope(shield=True):` around the clean-up means "don't cancel me in here". The producer gets my one deliberate cancel, httpx finishes closing, and the model stops (the fake now stops after 3 words). Lesson: in async code, **clean-up is the hard part**, and only a test that checks the other side (did the model actually stop?) catches this.

## Other work this week

- **Reading:** *AI Engineering* ch. 3, evaluation. My notes and the benchmark rows (semantic similarity, latency, valid output format, LLM as judge) are in my earlier ch. 3 note.
- **Reps (Mon 19 Oct, swapped with Friday):** first problem solved in O(n²) time and O(n) memory. Longest Substring Without Repeating Characters not solved; retry it unaided.

## What was hard

- Seeing what "module-level" state on the fake server meant, and why tests have to reset it before every test.
- Small bugs that broke everything quietly: a missing `await` on `_wait_or_give_up` (the coroutine never ran, so there was no retry and no error), and `float(value)` whose result I didn't keep.
- Keeping names in step across files (`read_time_out` versus `read_timeout`, and the error class names).

## What I'd do differently

- Write `classify` and its table test first. It made the retry loop small and easy to reason about.
- Run pyright after every function, not at the end. It flags an un-awaited coroutine and a possibly unbound variable before any test runs.
- Write the test that checks the *other side* (the model stopped, `FAKE.requests == 1`) early. Those tests found the real bugs.

## Carry into week 4 (API design)

- My `/ask` already has an API contract: request body, event types, error codes. Week 4 should make it explicit: versioning, documented error codes, and what's safe for clients to rely on.
- Not covered yet: a test for "ends without `[DONE]`", a test for the semaphore under load, and the optional circuit breaker (Part D).

## Hands-On RAG for Production, ch. 2

Full notes: [reading/hands-on-rag-ch02.md](reading/hands-on-rag-ch02.md)

- **Stages the chapter names:**
  - an ingestion flow: document parsing, chunking (fixed, fixed with overlap, recursive, semantic, document structure), embedding model selection, and the vector database and vector search
  - a generation flow: prompt engineering, and generating with the retrieved context
- **The one I've never built myself:** all of them in code. I know how RAG works, but the first I'll build is chunking plus hybrid retrieval in pgvector, on 5 November.
- **Questions for the 5 November lab:** which chunking method gives the best recall@k on the Malawi booklets? Where does recall@k stop improving as k grows? Does hybrid search beat vector-only search on questions with drug names and doses?