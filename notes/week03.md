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