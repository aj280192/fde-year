/**
 * Server-sent events over HTTP, as an async generator you can cancel.
 *
 * `streamEvents` works with every SSE endpoint (week 3's POST /ask, for one).
 * `streamTaskEvents` is the task API's events route, which returns 501 until a
 * worker exists: the client already handles that as an ApiError.
 */

import { ApiError, type ClientOptions, toApiError } from "./client.js";
import { parseSse, type SseEvent } from "./sse.js";

export type { SseEvent };

export async function* streamEvents(
  url: string,
  init: RequestInit,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
  // Under exactOptionalPropertyTypes, `signal` is added only when given.
  const res = await fetch(url, signal ? { ...init, signal } : init);
  if (!res.ok) throw await toApiError(res);
  if (!res.body) throw new ApiError(res.status, "NO_BODY", "the response has no body");
  yield* parseSse(res.body);
}

export function streamTaskEvents(
  opts: ClientOptions,
  taskId: string,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent> {
  return streamEvents(
    `${opts.baseUrl}/v1/tasks/${encodeURIComponent(taskId)}/events`,
    { headers: { "X-API-Key": opts.apiKey } },
    signal,
  );
}
