import { z } from "zod";
import type { components } from "./api.js";
export type Task = components["schemas"]["TaskOut"];

export const TaskState = z.enum(["queued" , "running" , "waiting_for_input" , "succeeded" , "failed" , "cancelled"])
export const TaskOutSchema = z.object({
    id: z.string(),
    state: TaskState,
    input: z.string(),
    result: z.string().nullable().exactOptional(),
    error: z.object({
        code: z.string(),
        message: z.string()
    }).nullable().exactOptional(),
    created_at: z.string(),
    updated_at: z.string(),
});

type Inferred = z.infer<typeof TaskOutSchema>;
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
export const schemaMatchesSpec: Same<Inferred, Task> = true;

