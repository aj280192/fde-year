import { z } from "zod";
import { TaskOutSchema } from "./schemas.js"
import type { StringValidation } from "zod/v3";

export interface ClientOptions {
  baseUrl: string;   // "http://localhost:8000"
  apiKey: string;    // from process.env, never written in code
}

export class ApiError extends Error {
  constructor(readonly status: number, readonly reason: string, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export const ErrorResponseSchema = z.object({
    error: z.object({
        code: z.string(),
        status: z.string(),
        message: z.string(),
        details: z.array(z.object({
            reason: z.string(),
        })),
    }),
});

export const TaskPageSchema = z.object({
    tasks: z.array(TaskOutSchema),
    next_page_token: z.string()
});

export type ErrorResponse = z.infer<typeof ErrorResponseSchema>;
export type TaskPageSchema = z.infer<typeof TaskPageSchema>;
export type TaskOut = z.infer<typeof TaskOutSchema>;

export async function toApiError(res: Response): Promise<ApiError>{
    let body: unknown;

    try {
        body = await res.json();
    } catch {
        return new ApiError(res.status, "UNKNOWN", res.statusText);
    }

    const parsed = ErrorResponseSchema.safeParse(body);

    if (!parsed.success){
        return new ApiError(res.status, "UNKNOWN", res.statusText);
    }

    const {details, message} = parsed.data.error;
    const reason = details[0]?.reason ?? "UNKNOWN";

    return new ApiError(res.status, reason, message);
}
export interface RequestOptions{
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal | undefined;
}

export async function request(opts: ClientOptions, method: string, path: string, ro: RequestOptions = {}): Promise<unknown> {
       const init: RequestInit = {
        method,
        headers: { "X-API-Key": opts.apiKey, "Content-Type": "application/json", ...ro.headers,},
       };
       
       if (ro.body !== undefined) init.body = JSON.stringify(ro.body);
       if (ro.signal) init.signal = ro.signal;

       const res = await fetch(opts.baseUrl + path, init);
       if (!res.ok) throw await toApiError(res);

       const data: unknown = await res.json();
       return data;
}

export async function createTask(
    opts: ClientOptions,
    input: unknown,
{
    idempotencyKey,
    signal,
}: { idempotencyKey?: string; signal?: AbortSignal | undefined} = {},
): Promise<TaskOut>{
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

    const ro: RequestOptions = { body: { input }, headers };
    if (signal) ro.signal = signal;

    const data = await request(opts, "POST", "/v1/tasks", ro);
    return TaskOutSchema.parse(data);
}  

export async function getTask(
    opts: ClientOptions,
    taskId: string,
    { signal }: { signal?: AbortSignal | undefined } = {},
): Promise<TaskOut> {
    const ro: RequestOptions = {};
    if (signal) ro.signal = signal;

    const data = await request(
        opts,
        "GET",
        `/v1/tasks/${encodeURIComponent(taskId)}`,
        ro,
    );
    return TaskOutSchema.parse(data);
}

export async function listTasks(
    opts: ClientOptions,
    {
        pageSize,
        pageToken,
        signal,
    }: {
        pageSize?: number;
        pageToken?: string;
        signal?: AbortSignal | undefined;
    } = {},
): Promise<TaskPageSchema> {
    const q = new URLSearchParams();
    if (pageSize !== undefined) q.set("page_size", String(pageSize));
    if (pageToken) q.set("page_token", pageToken);
    const suffix = q.size > 0 ? `?${q.toString()}` : "";

    const ro: RequestOptions = {};
    if (signal) ro.signal = signal;

    const data = await request(opts, "GET", `/v1/tasks${suffix}`, ro);
    return TaskPageSchema.parse(data);
}