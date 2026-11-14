import assert from "node:assert/strict";
import { test } from "node:test";
import { parseSse, type SseEvent } from "./sse.js";

/** A response body that delivers exactly these chunks. */
function bodyFrom(chunks: (string | Uint8Array)[], onCancel?: () => void): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(c) {
      for (const s of chunks) c.enqueue(typeof s === "string" ? enc.encode(s) : s);
      c.close();
    },
    cancel() {
      onCancel?.();
    },
  });
}

async function collect(body: ReadableStream<Uint8Array>): Promise<SseEvent[]> {
  const out: SseEvent[] = [];
  for await (const e of parseSse(body)) out.push(e);
  return out;
}

test("an event split across chunks, a ping, and \\r\\n line endings", async () => {
  const events = await collect(
    bodyFrom([
      "event: tok", // "token" is split across chunks 1 and 2
      'en\ndata: {"text":"Hi"}\n',
      "\n: ping\n\n", // the blank line ending event 1 is split across chunks 2 and 3
      'event: done\r\ndata: {"usage":null}\r\n\r\n',
    ]),
  );
  assert.deepEqual(events, [
    { event: "token", data: { text: "Hi" } },
    { event: "done", data: { usage: null } },
  ]);
});

test("a two-byte character split across chunks", async () => {
  const bytes = new TextEncoder().encode('data: {"t":"é"}\n\n');
  const cut = bytes.indexOf(0xc3) + 1; // inside the two bytes of é
  const events = await collect(bodyFrom([bytes.slice(0, cut), bytes.slice(cut)]));
  assert.deepEqual(events, [{ event: "message", data: { t: "é" } }]);
});

test("several data lines join with a newline", async () => {
  const events = await collect(bodyFrom(['data: ["a",\ndata: "b"]\n\n']));
  assert.deepEqual(events, [{ event: "message", data: ["a", "b"] }]);
});

test("breaking out early closes the stream", async () => {
  let cancelled = false;
  const body = bodyFrom(['data: 1\n\n', 'data: 2\n\n'], () => {
    cancelled = true;
  });
  for await (const e of parseSse(body)) {
    assert.deepEqual(e, { event: "message", data: 1 });
    break;
  }
  assert.equal(cancelled, true);
});
