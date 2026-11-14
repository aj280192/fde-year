/**
 * Server-sent events (SSE): turn a stream of bytes into a stream of events.
 *
 * On the wire, each event is a few `field: value` lines ended by a blank line:
 *
 *     event: token
 *     data: {"text":"Pods"}
 *
 *     : ping            <- a comment (week 3's heartbeat): skipped
 *
 * The network delivers chunks that can end anywhere, even inside a line or a
 * character, so the parser keeps a buffer and only emits complete events.
 */

export interface SseEvent {
  /** "token", "done", "error"; "message" when the event has no `event:` line. */
  event: string;
  /** The `data:` lines parsed as JSON. Not yet checked: validate before use. */
  data: unknown;
}

/** One block of lines (between blank lines) into one event, or undefined if it has no data. */
function toEvent(block: string): SseEvent | undefined {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) continue; // blank line or comment
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, ""); // drop one leading space
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (data.length === 0) return undefined;
  return { event, data: JSON.parse(data.join("\n")) as unknown };
}

/** Yield each complete event in `body`. Breaking out early, an abort or an error all close the stream. */
export async function* parseSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      // stream: true keeps a multi-byte character split across chunks until its last byte arrives.
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");
      const blocks = buffer.split("\n\n");
      // The last piece may be an event whose end hasn't arrived yet: keep it for the next chunk.
      buffer = done ? "" : (blocks.pop() ?? "");
      for (const block of blocks) {
        const e = toEvent(block);
        if (e) yield e;
      }
      if (done) return;
    }
  } finally {
    // Runs on a normal end, on `break` in the caller's for-await, on abort and on error:
    // cancelling closes the connection, so the server stops sending.
    await reader.cancel().catch(() => undefined);
  }
}
