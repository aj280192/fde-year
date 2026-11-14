/**
 * The client against the real week 4 task API.
 *
 *   uv run python labs/week04/api/auth.py                          # prints a key and its hash
 *   TASKS_API_KEY_HASH=<hash> uv run python labs/week04/serve.py
 *   TASKS_API_KEY=<key> npx tsx src/demo.ts
 */
import { ApiError, type ClientOptions, createTask, getTask, listTasks } from "./client.js";
import { streamTaskEvents } from "./stream.js";

const apiKey = process.env["TASKS_API_KEY"];
if (!apiKey) throw new Error("set TASKS_API_KEY");
const opts: ClientOptions = { baseUrl: process.env["TASKS_API_URL"] ?? "http://localhost:8000", apiKey };

// 1 · Create, then create again with the same idempotency key: the same task comes back.
const first = await createTask(opts, "Diagnose: payments pods crash-looping", { idempotencyKey: "demo-1" });
const replay = await createTask(opts, "Diagnose: payments pods crash-looping", { idempotencyKey: "demo-1" });
console.log("created", first.id, first.state, "| replay gives the same id:", first.id === replay.id);

// 2 · A second task, then read the first one back.
await createTask(opts, "Summarise yesterday's failed deployments");
console.log("got", first.id, (await getTask(opts, first.id)).state);

// 3 · Two pages of one task each (newest first).
const page1 = await listTasks(opts, { pageSize: 1 });
const page2 = await listTasks(opts, { pageSize: 1, pageToken: page1.next_page_token });
console.log("page 1:", page1.tasks.map((t) => t.id), "| page 2:", page2.tasks.map((t) => t.id));

// 4 · Errors arrive as ApiError, with the API's stable `reason`.
async function expectApiError(label: string, call: () => Promise<unknown>): Promise<void> {
  try {
    await call();
    console.log(label, "unexpectedly succeeded");
  } catch (e) {
    if (!(e instanceof ApiError)) throw e; // anything else is a real bug: don't hide it
    console.log(label, "→ ApiError", e.status, e.reason);
  }
}
await expectApiError("get a missing task", () => getTask(opts, "t_missing"));
await expectApiError("stream task events", async () => {
  for await (const e of streamTaskEvents(opts, first.id)) console.log(e);
});
