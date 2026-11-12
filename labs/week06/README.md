# Week 6 · TypeScript, the language

Python to TypeScript, under `strict` from the first file. The TypeScript Handbook typed out by hand, the
week 2 tool models rebuilt in Zod, and (Thursday) a typed client for the week 4 task API.

| File | What it covers |
| --- | --- |
| `01-basics.ts` … `09-utility-types.ts` | the TypeScript Handbook, typed out under `strict`; each deliberate error left as a comment with its message |
| `zod-tools.ts` | the week 2 tool models (`ToolSpec`, `ToolCall`, `ToolResult`) as Zod schemas; every type derived with `z.infer` |
| `payloads.ts` | the six invalid payloads from week 2, shared by the script and the tests |
| `zod-payloads.ts` | runs the payloads through Zod and prints every issue |
| `zod-payloads.test.ts` | the same, as tests |

```bash
npm install
npm run check      # type-check everything, under strict
npm test           # run every *.test.ts
npx tsx zod-payloads.ts
```

## The setup

`tsconfig.json` turns on `strict`, plus three checks it doesn't include:

| Setting | Effect |
| --- | --- |
| `noUncheckedIndexedAccess` | `arr[0]` is `T \| undefined`, so it must be checked before use |
| `exactOptionalPropertyTypes` | an optional property may be absent, but can't be set to `undefined` |
| `verbatimModuleSyntax` | type-only imports must say `import type` |

`tsx` runs a file **without checking its types**; `tsc --noEmit` (`npm run check`) checks them and runs
nothing. Types are erased at runtime, so data from outside is checked with Zod.

## Zod against Pydantic: the same six invalid payloads

The six payloads from `labs/week02/toolkit/tests/test_models.py`, through the week 2 Pydantic models and
through Zod 4. Both columns are real output.

| # | Payload | Pydantic (week 2) | Zod 4 |
| --- | --- | --- | --- |
| 1 | `ToolCall` with no `name` | `name` · `missing` · "Field required" | `name` · `invalid_type` · "expected string, received undefined" |
| 2 | `arguments` is a string | `arguments` · `dict_type` · "Input should be an object" | `arguments` · `invalid_type` · "expected record, received string" |
| 3 | an extra field | `extra_field` · `extra_forbidden` | the object itself (`[]`) · `unrecognized_keys`, with `keys: ["extra_field"]` |
| 4 | `kind: "done"` | `outcome` · `union_tag_invalid` · "does not match any of the expected tags: 'success', 'error'" | `outcome.kind` · `invalid_union` · "Invalid discriminator value. Expected 'success' \| 'error'" |
| 5 | an error with `content` and no `message` | **two errors:** `outcome.error.content` · `extra_forbidden`, and `outcome.error.message` · `missing` | **two errors:** `outcome` · `unrecognized_keys` (`content`), and `outcome.message` · `invalid_type` |
| 6 | `name` is a number | `name` · `string_type` · "Input should be a valid string" | `name` · `invalid_type` · "expected string, received number" |

**What I noticed:**

- **Both rejected all six, for the same reasons.** The differences are in how they report it, not in
  what they catch.
- **Pydantic's error codes are more specific.** It has a code for each problem (`missing`, `dict_type`,
  `string_type`), so code can react to the exact problem. Zod uses one broad `invalid_type` for three of
  them and puts the detail ("expected string, received undefined") in the message, which is easier to
  read but harder to branch on.
- **Extra keys are reported in different places.** Pydantic puts the bad key in the path
  (`extra_field`). Zod points at the object that has it (`[]`, or `outcome`) and lists the keys in a
  separate `keys` field. Pydantic's form is easier to show next to a form field; Zod's groups several
  extra keys into one issue.
- **Pydantic names the union variant in the path; Zod doesn't.** Pydantic says
  `outcome.error.content`, so you can see which variant it checked against. Zod says `outcome.message`.
- **Payload 5 has two problems, and both libraries report both.** My week 2 test only asserted on
  `errors()[0]`, so it never showed the missing `message`. A test should check every error, not just
  the first: the week 6 tests compare the full, sorted list.
- **A discriminated union fails on the tag first, in both.** With `kind: "done"`, neither library
  reports the fields of every variant; both say the tag is wrong and list the allowed values. That's
  the reason to use a discriminated union rather than a plain union.
- **One structural difference.** In Pydantic, one class is both the runtime check and the type. In
  TypeScript the types don't exist at runtime, so Zod splits them: the schema is a value that checks
  data, and `z.infer<typeof Schema>` derives the type from it. Writing the type by hand as well would
  let the two drift apart, so I don't.
- **Defaults to remember.** Zod's plain `z.object` silently **drops** unknown keys (like Pydantic's
  default `extra="ignore"`); `z.strictObject` rejects them (`extra="forbid"`). And Zod never converts
  `"5"` to `5` unless asked (`z.coerce`), which matches Pydantic's `strict=True`.