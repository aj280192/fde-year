import assert from "node:assert/strict";
import { test } from "node:test";
import type { z } from "zod";
import { CASES } from "./payloads.js";
import { ToolResult, summarise } from "./zod-tools.js";

type Found = readonly [path: string, code: string];

/** Every issue as [path, code], sorted, so the comparison doesn't depend on order. */
function issuesOf(schema: z.ZodType, json: string): Found[] {
  const result = schema.safeParse(JSON.parse(json));
  assert.equal(result.success, false, "the payload should be invalid");
  if (result.success) return [];
  return result.error.issues
    .map((i): Found => [i.path.map(String).join("."), i.code])
    .sort((a, b) => a.join().localeCompare(b.join()));
}

const EXPECTED: Record<number, Found[]> = {
  1: [["name", "invalid_type"]],
  2: [["arguments", "invalid_type"]],
  3: [["", "unrecognized_keys"]],
  4: [["outcome.kind", "invalid_union"]],
  5: [["outcome", "unrecognized_keys"], ["outcome.message", "invalid_type"]],
  6: [["name", "invalid_type"]],
};

for (const c of CASES) {
  test(`payload ${c.id}: ${c.label}`, () => {
    assert.deepEqual(issuesOf(c.schema, c.json), EXPECTED[c.id]);
  });
}

test("payload 3 names the extra key", () => {
  const c = CASES[2];
  assert.ok(c);
  const result = c.schema.safeParse(JSON.parse(c.json));
  if (result.success) return assert.fail("should be invalid");
  const issue = result.error.issues[0];
  assert.ok(issue && issue.code === "unrecognized_keys");
  assert.deepEqual(issue.keys, ["extra_field"]);
});

test("a valid result parses and summarises", () => {
  const result = ToolResult.safeParse({
    call_id: "c1",
    outcome: { kind: "success", content: "3 pods restarted" },
  });
  assert.equal(result.success, true);
  if (!result.success) return;
  assert.equal(summarise(result.data), "ok: 3 pods restarted");
});