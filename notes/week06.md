# Week 6 · Python to TypeScript

A lookup sheet for moving between the two languages, under `strict`. Examples come from `labs/week06/`.

**Core idea.** TypeScript types are checked at compile time and erased before the code runs. Zod checks data at run time, at the edges where data comes in. The two cover different gaps, and you need both.

## 1 · Compile time against run time

| Question | Compile time (`tsc`) | Run time (Zod) |
| --- | --- | --- |
| Does my code use its own types consistently? | yes | no |
| Is this JSON from the API really what I said it was? | **no**, `as T` and `res.json()` are not checks | yes, `schema.parse(data)` |
| Does a typo in a field name get caught? | yes, in my code | only if the schema is strict |
| Is the value in range, the right length, an email? | no | yes (`.min()`, `.email()`, ...) |
| Does it cost anything at run time? | nothing, types are erased | yes, a small cost per parse |
| What happens on a mismatch? | build error | `ZodError` thrown, or `{ success: false }` |

Rules that follow:

- Every response from outside the program (HTTP, files, env vars, `JSON.parse`, SSE events) is `unknown` until a schema has checked it.
- Derive the type from the schema, `z.infer<typeof S>`. Never write the type by hand as well, or the two drift apart.
- `tsx` runs code **without** checking types. `npm run check` (`tsc --noEmit`) checks types and runs nothing. Run both.
- A schema checks **shape**, not rules of the business (is this user allowed, is the ID real). Those are still my code.

## 2 · Python to TypeScript table

| # | Python | TypeScript | Watch out |
| --- | --- | --- | --- |
| 1 | `int`, `float` | `number` (and `bigint`) | one type, a 64-bit float. `0.1 + 0.2 !== 0.3`. Integers above 2^53 lose precision, so big IDs in JSON break |
| 2 | `str` | `string` | `'a'`, `"a"` and `` `a` `` are the same type. `.length` counts UTF-16 units, so an emoji has length 2 |
| 3 | `bool` | `boolean` | see truthiness in section 4 |
| 4 | `None` | `null` **and** `undefined` | two kinds of nothing. A missing key, an unset variable and a function with no return give `undefined`; `null` is set on purpose |
| 5 | `list[int]` | `number[]` | `arr[99]` gives `undefined`, never an error. `noUncheckedIndexedAccess` makes the type `number \| undefined` |
| 6 | `tuple[str, int]` | `[string, number]` | a plain array at run time. The length is not enforced when data comes in |
| 7 | `dict[str, int]` | `Record<string, number>` | keys are always strings (`1` becomes `"1"`). `"toString" in obj` is true. Use `Map` for real dynamic keys |
| 8 | `set[int]` | `Set<number>` | objects are compared by reference, so two equal-looking objects are two entries |
| 9 | `Optional[str]` | `string \| undefined` (or `\| null`) | TypeScript separates missing, `undefined` and `null`. Choose one per field and say which |
| 10 | `int \| str` | `number \| string` | must be narrowed (`typeof`) before use |
| 11 | `Literal["a", "b"]` | `"a" \| "b"` | `let x = "a"` widens to `string`. Use `const`, or `as const` on objects |
| 12 | `Enum` | `as const` object plus a union type | avoid `enum`: it emits run-time code and behaves oddly |
| 13 | `TypedDict` | `interface` or `type` | gone at run time, so no `instanceof` on an interface |
| 14 | frozen `@dataclass` | `readonly` properties, `Readonly<T>` | compile time only. `Object.freeze` is run time, and shallow |
| 15 | `NotRequired[int]` | `field?: number` | under `exactOptionalPropertyTypes` the field may be absent but can't be set to `undefined` |
| 16 | `isinstance(x, str)` | `typeof x === "string"`, `instanceof`, `"k" in x`, `Array.isArray` | `typeof null === "object"`, and `typeof []` is also `"object"` |
| 17 | `TypeGuard[T]` | `(x: unknown): x is T` | the compiler trusts the function. If its body is wrong, the type is wrong and nothing warns you |
| 18 | `match` with `assert_never` | `switch (x.kind)` with a `never` check in `default` | no fallthrough guard: each case needs `return` or `break` |
| 19 | `Callable[[str], None]` | `(s: string) => void` | a `void` callback type accepts a function that returns something. A callback may take fewer parameters than declared |
| 20 | `*args`, `**kwargs` | `...args: T[]`, or one options object | no `**kwargs`: pass an object, and type it |
| 21 | default `def f(x=5)` | `function f(x = 5)` | the default applies for `undefined` only, not `null`. It is rebuilt per call, so no shared-mutable-default trap |
| 22 | `@overload` | overload signatures plus one implementation | the implementation signature is not visible to callers |
| 23 | `def f[T](x: T)` | `function f<T>(x: T)` | erased at run time: no `T()`, no `x instanceof T` |
| 24 | `cast(T, x)` | `x as T` | no check at all. It silences the compiler and lies. Prefer a Zod parse |
| 25 | `Any` and `object` | `any` and `unknown` | `any` switches checking off and spreads. `res.json()` returns `any`, so assign it to `unknown` at once |
| 26 | `async def`, `await` | `async function`, `await` | a forgotten `await` leaves a Promise, which is **truthy**. `forEach(async ...)` does not wait. `Promise.all` rejects on the first failure |
| 27 | `async for`, async generator | `for await`, `async function*` | `break` calls the generator's `return`, so its `finally` runs. This is how `streamEvents` cleans up |
| 28 | cancelling a task | `AbortController` and `AbortSignal` | cancelling is cooperative. `fetch` rejects with an `AbortError`: tell it apart from a real failure |
| 29 | Pydantic `BaseModel` | Zod schema and `z.infer` | the schema is a value that checks data. The type is derived, not the other way round |
| 30 | `extra="forbid"` | `z.strictObject` | plain `z.object` **drops** unknown keys silently (Pydantic's default `ignore`). Use `z.object` for server responses and `strictObject` for what I send |
| 31 | `model_validate_json(s)` | `schema.parse(JSON.parse(s))` | two places to fail: `JSON.parse` throws, then Zod throws. `safeParse` returns `{ success, data \| error }` and does not throw |
| 32 | `raise`, `except E` | `throw`, `catch (e)` | anything can be thrown, and `e` is `unknown`. Narrow with `instanceof` before reading `e.message` |
| 33 | `class E(Exception)` | `class E extends Error` | set `name`. Pass `{ cause }` to keep the original error |
| 34 | pyright strict | `tsc --noEmit` with `strict` | `tsx` skips this step entirely |
| 35 | pytest | `node:test` with `node:assert` | files named `*.test.ts`, run through `tsx`. Async tests must be awaited or returned |
| 36 | `uv`, `pyproject.toml` | `npm`, `package.json`, `tsconfig.json` | `"type": "module"`. Under `nodenext`, local imports end in `.js` even for `.ts` files |
| 37 | `==` | `===` | `==` converts types: `0 == ""` is true. Always use `===` |
| 38 | `a or b` | `a ?? b` (not `a \|\| b`) | `\|\|` also replaces `0`, `""` and `false`. `??` replaces only `null` and `undefined` |
| 39 | f-string | template literal | `${obj}` prints `[object Object]`. Use `JSON.stringify` |
| 40 | `sorted(xs)` | `xs.toSorted((a, b) => a - b)` | `xs.sort()` **mutates** and sorts as **strings**: `[10, 9, 1].sort()` gives `[1, 10, 9]` |
| 41 | `for x in xs` | `for (const x of xs)` | `for...in` loops over keys (strings), not values |
| 42 | `{k: v for ...}` | `Object.fromEntries(xs.map(...))` | no comprehensions |
| 43 | `datetime` | `Date` | months count from 0. `new Date("2026-11-16")` is parsed as UTC, but `new Date("2026-11-16T00:00")` as local time |
| 44 | `//` and `%` | `Math.trunc(a / b)` and `%` | `/` is always a float. `-7 % 3` is `-1` (the sign follows the left side) |

## 3 · No clean equivalent

**TypeScript has it, Python doesn't**

- **Mapped, conditional and template-literal types.** Types computed from other types (`Partial<T>`, `keyof T`, `` `on${string}` ``). Python can't compute types.
- **Structural typing as the default.** Any object with the right shape fits, with no inheritance needed. Python mostly uses names (`Protocol` is the exception).
- **`exactOptionalPropertyTypes` and `noUncheckedIndexedAccess`.** Strictness flags that change what a type means.
- **`satisfies` and `as const`.** Check against a type without widening it, and freeze literal types.

**Python has it, TypeScript doesn't**

- **Annotations that can be read at run time.** Pydantic works because Python keeps annotations. TypeScript erases them, which is why Zod exists.
- **Generated equality and ordering** (`@dataclass`). Objects and arrays compare by reference; `[] === []` is false.
- **A large standard library and tidy built-in types.** Here: npm packages, and `Map`/`Set` that need care.
- **Real integers, and `//`.** One `number` for everything.

## 4 · Edge cases to keep in mind

**Truthiness and equality**

- Falsy: `0`, `""`, `NaN`, `null`, `undefined`, `false`. Unlike Python, **`[]` and `{}` are truthy**.
- `NaN !== NaN`. Use `Number.isNaN(x)`.
- `typeof null === "object"`. Check `x === null` first.
- Objects and arrays compare by reference. For deep equality: `JSON.stringify` (fragile), or `node:util` `isDeepStrictEqual`.

**Numbers and conversion**

- `Number("")` and `Number(" ")` are `0`. `Number("12px")` is `NaN`. `parseInt("12px")` is `12`.
- `z.coerce.number()` uses `Number()`, so `""` becomes `0` and passes. Don't coerce form fields without a `.min(1)` or a check for empty.
- `z.coerce.boolean()` uses `Boolean()`, so the string `"false"` becomes `true`.
- `z.number()` rejects `NaN`. Zod 4 also rejects `Infinity`. Use `z.int()` when it must be a whole number.
- IDs bigger than 2^53 arrive from JSON as a rounded number. Send them as strings.

**Missing, `undefined` and `null`**

- Three states: key missing, key present with `undefined`, key present with `null`. `"k" in obj` and `obj.k === undefined` give different answers.
- `JSON.stringify` **drops** keys whose value is `undefined`, turns `undefined` inside arrays into `null`, and turns `NaN` into `null`.
- With `exactOptionalPropertyTypes`, add optional properties only when defined: `...(x !== undefined && { x })`.
- `?.` stops the chain and returns `undefined`. It also hides typos in a chain, so don't use it everywhere.

**Arrays and objects**

- `arr[99]` is `undefined`, with no error. Check it, or let `noUncheckedIndexedAccess` remind you.
- `sort()` mutates and compares strings. `toSorted` copies. A comparator must return a number, not a boolean.
- `readonly` and `as const` are compile time only. At run time nothing stops a write.
- Excess property checks run **only on fresh object literals**. `const o = {a: 1, extra: 2}; f(o)` passes even if `f` wants `{a: number}`.
- `Map` and `Set` become `{}` through `JSON.stringify`.
- Spread (`{...a}`) is a **shallow** copy. Nested objects are shared.

**Async**

- A function that forgets `await` returns a Promise, which is truthy. `if (check())` always passes.
- `array.forEach(async ...)` doesn't wait. Use `for...of` with `await`, or `Promise.all(xs.map(...))`.
- An unhandled rejection can end the Node process. Every Promise gets an `await` or a `.catch`.
- `AbortError` is not a failure of the server. Check the error's `name` before reporting it.
- `fetch` does **not** reject on a 404 or 500. Check `res.ok` yourself, then parse the body.

**Zod**

- `z.object` drops unknown keys, `strictObject` rejects them, `looseObject` keeps them. Pick on purpose.
- `.optional()` accepts a present `undefined`; `.exactOptional()` doesn't. `.nullable()` is a different thing again.
- `z.infer` is the **output** type; after a `.transform` or `.default` it differs from the input. Use `z.input` for what callers send.
- `parse` throws and `safeParse` returns. Don't mix them in one place. Handle the throw once, at the edge.
- Check **every** issue in tests, not just the first. Payload 5 had two.
- Parsing is a copy: the result is new data, so `parse` before use and keep using the result.

**Dates and strings**

- `new Date("2026-11-16")` is UTC midnight; add a time and it becomes local. Over a day boundary in Singapore (UTC+8) this shifts the date.
- `"😀".length` is 2. Use `[..."😀"].length` to count characters.
- Comparing strings with `<` uses UTF-16 order. Use `localeCompare` for names.

**Modules and tooling**

- Under `nodenext`, write `import { x } from "./y.js"` for a file called `y.ts`. Importing `.ts` gives error TS5097.
- `verbatimModuleSyntax`: type-only imports need `import type`, or the build fails.
- `tsx` doesn't check types. A green run means nothing about types.
- `catch (e)` gives `unknown`. `e instanceof Error` before `e.message`.

**Streaming (SSE) client**

- A network chunk can end in the middle of an event or a UTF-8 character. Keep the unfinished tail in a buffer, and use `TextDecoder` with `{ stream: true }`.
- An event can have several `data:` lines, and line endings can be `\n` or `\r\n`.
- Always release the reader in `finally` (`reader.cancel()`), or the connection stays open when the consumer stops early.
- An unknown event type or a payload that fails its schema is an error to handle, not to ignore.

## 5 · What surprised me this week

- `tsx` ran code that did not type-check. Running and checking are two different commands, so I run both.
- Pydantic and Zod both reported **two** errors for payload 5. My week 2 test only looked at the first, so it never saw the second.
- `res.json()` is `any`, so the type can look right while the data isn't. A cast just hides that; Zod is what checks it.