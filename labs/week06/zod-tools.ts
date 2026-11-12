import { z } from "zod";

// 1. The schema: a real object that exists at runtime and can check data
export const ToolSpec = z.strictObject({
    name: z.string(),
    description: z.string(),
    input_schema: z.record(z.string(), z.json()),
});
export const ToolCall = z.strictObject({
    id: z.string(),
    name: z.string(),
    arguments: z.record(z.string(), z.json())
})

// 2. The type: worked out from the schema at compile time
export type ToolSpec = z.infer<typeof ToolSpec>;
export type ToolCall = z.infer<typeof ToolCall>;
// = {name: string; description: string, input_schema: Record<string, JSONType>}

// z.object -> extra="ignore"
// z.strictObject -> extra="forbid"
// z.looseObject -> extra="allow"

// z.number() -> only allow 5 not "5"
// z.coerce.number() -> 5 or "5"
// ToolCall.parse(data);        // returns typed data, or THROWS a ZodError
// ToolCall.safeParse(data);    // never throws; returns an object you check

// const result = ToolCall.safeParse(JSON.parse(text));
// if (result.success) {
//   result.data.name;              // typed: ToolCall
// } else {
//   result.error.issues;           // each issue: path, code, message
// }


const ToolSuccess = z.strictObject({ kind: z.literal("success"), content: z.string() });
const ToolError   = z.strictObject({ kind: z.literal("error"),   message: z.string() });
const ToolOutcome = z.discriminatedUnion("kind", [ToolSuccess, ToolError]);

type ToolOutcome = z.infer<typeof ToolOutcome>;
// { kind: "success"; content: string } | { kind: "error"; message: string }

export const ToolResult = z.strictObject({
    call_id: z.string(),
    outcome: ToolOutcome
})

type ToolResult = z.infer<typeof ToolResult>;

export function summarise(r: ToolResult): string {
  switch (r.outcome.kind) {
    case "success":
      return `ok: ${r.outcome.content}`;     // only the success variant has content
    case "error":
      return `failed: ${r.outcome.message}`; // only the error variant has message
    default: {
      const unreachable: never = r.outcome;  // fails to compile if a variant isn't handled
      return unreachable;
    }
  }
}