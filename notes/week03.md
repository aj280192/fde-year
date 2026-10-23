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