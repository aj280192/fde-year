// Types from Types
// ---- Keyof ----
type Point = { x: number; y: number };
type P = keyof Point;                   // "x" | "y"

// ---- Typeof ----
const config = { retries: 3, timeoutSeconds: 10 };
type Config = typeof config;            // { retries: number; timeoutSeconds: number }
function f() { return { ok: true, n: 1 }; }
type R = ReturnType<typeof f>;          // preview of W4

// ---- Index access ----
type Person = { name: string; age: number; tags: string[] };
type Age = Person["age"];               // number
type Tag = Person["tags"][number];      // string: an array's element type

// ---- Conditional types ----
type IsString<T> = T extends string ? "yes" : "no";
type A = IsString<"hi">;                // "yes"
type B = IsString<42>;                  // "no"

type ElementOf<T> = T extends (infer U)[] ? U : never;
type E = ElementOf<number[]>;           // number: `infer` pulls a type out