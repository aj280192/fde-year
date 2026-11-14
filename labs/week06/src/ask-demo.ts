/**
 * streamEvents against week 3's real SSE endpoint, then an abort partway.
 *
 *   cd labs/week03
 *   uv run uvicorn fake_upstream:app --port 9000
 *   LLM_BASE_URL=http://127.0.0.1:9000/v1 uv run python serve.py      # /ask on port 8000
 *   npx tsx src/ask-demo.ts                                            # from labs/week06
 */
import { streamEvents } from "./stream.js";

const url = process.env["ASK_URL"] ?? "http://127.0.0.1:8000/ask";
const init: RequestInit = {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: "Why do pods restart?" }),
};

// 1 · A whole answer: print the text as it arrives, then the final event.
let count = 0;
let answer = "";
for await (const e of streamEvents(url, init)) {
  count += 1;
  if (e.event === "token" && typeof e.data === "object" && e.data !== null && "text" in e.data) {
    answer += String(e.data.text);
  } else {
    console.log(e.event, JSON.stringify(e.data));
  }
}
console.log(`answer: ${answer}\nevents: ${count}`);

// 2 · Abort after the first event.
const controller = new AbortController();
try {
  for await (const e of streamEvents(url, init, controller.signal)) {
    console.log("first event, then abort:", e.event);
    controller.abort();
  }
} catch (err) {
  console.log("stopped with", err instanceof Error ? err.name : String(err));
}
