import { z } from "zod";
import { CASES } from "./payloads.js";

for (const c of CASES) {
  const data: unknown = JSON.parse(c.json);
  const result = c.schema.safeParse(data);

  console.log(`\n#${c.id} · ${c.label}`);
  if (result.success) {
    console.log("  unexpectedly valid");
    continue;
  }
  for (const issue of result.error.issues) {
    const keys = issue.code === "unrecognized_keys" ? `  keys=${JSON.stringify(issue.keys)}` : "";
    console.log(`  path=${JSON.stringify(issue.path)}  code=${issue.code}${keys}`);
    console.log(`    ${issue.message}`);
  }
  if (c.id === 5) {
    console.log(z.prettifyError(result.error).replace(/^/gm, "    "));
  }
}