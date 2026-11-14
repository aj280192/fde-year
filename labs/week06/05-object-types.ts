// TypeScript Handbook · Object Types
// Run: npx tsx 05-object-types.ts    Check: npm run check
// Each deliberate error is left as a comment, with the compiler's message.

// ---- Optional properties, with defaults through destructuring ----
interface PaintOptions {
  shape: string;
  color?: string;
  xPos?: number;
  yPos?: number;
}

function paint({ shape, color = "black", xPos = 0, yPos = 0 }: PaintOptions): string {
  // Inside, the defaults make these plain `string` and `number`, not `| undefined`.
  return `${color} ${shape} at (${xPos}, ${yPos})`;
}
console.log(paint({ shape: "circle" }));
console.log(paint({ shape: "square", color: "red", xPos: 3 }));

// ---- readonly ----
interface Home {
  readonly owner: string;
}
const home: Home = { owner: "Ajay" };
// home.owner = "someone else";
//   TS2540: Cannot assign to 'owner' because it is a read-only property.
// readonly is checked by the compiler only: at runtime the object is ordinary (Object.freeze is the runtime version).

// ---- Index signatures ----
interface Scores {
  [name: string]: number;
}
const scores: Scores = { mei: 3, ravi: 5 };
const ravi = scores["ravi"]; // number | undefined, because of noUncheckedIndexedAccess
console.log("ravi:", ravi ?? "no score");
// const sure: number = scores["siti"];
//   TS2322: Type 'number | undefined' is not assignable to type 'number'.
// Like dict.get() in Python: a key may be missing, so the type says so.

// ---- Excess property checks, and their limit ----
// paint({ shape: "circle", colour: "red" });
//   TS2561: Object literal may only specify known properties, but 'colour' does not exist
//   in type 'PaintOptions'. Did you mean to write 'color'?
const fromVariable = { shape: "circle", colour: "red" };
console.log(paint(fromVariable)); // no error: the check only applies to an object literal written in the call
// That limit is why data from outside is validated at runtime (Zod), not just typed.

// ---- Extending types ----
interface Address {
  street: string;
  city: string;
}
interface Address3D extends Address {
  floor: number;
}
const office: Address3D = { street: "1 Example Rd", city: "Singapore", floor: 12 };
console.log(`${office.city}, floor ${office.floor}`);

// ---- Intersection types ----
interface Colorful {
  color: string;
}
interface Circle {
  radius: number;
}
type ColorfulCircle = Colorful & Circle;
const badge: ColorfulCircle = { color: "red", radius: 4 };
// const half: ColorfulCircle = { color: "red" };
//   TS2322: Type '{ color: string; }' is not assignable to type 'Colorful & Circle'.
//   Property 'radius' is missing in type '{ color: string; }' but required in type 'Circle'.
console.log(badge);

// ---- Generic object types ----
interface Box<T> {
  contents: T;
}
const numberBox: Box<number> = { contents: 42 };
const taskBox: Box<{ id: string; state: "queued" | "running" }> = { contents: { id: "t_1", state: "queued" } };
// const wrong: Box<number> = { contents: "x" };
//   TS2322: Type 'string' is not assignable to type 'number'.
console.log(numberBox.contents, taskBox.contents.state);

// ---- ReadonlyArray ----
function joinAll(parts: ReadonlyArray<string>): string {
  // parts.push("x");
  //   TS2339: Property 'push' does not exist on type 'readonly string[]'.
  return parts.join(", ");
}
console.log(joinAll(["a", "b", "c"]));

// ---- Tuples ----
type Pair = [name: string, score: number];
const pair: Pair = ["Mei", 3];
const [name, score] = pair;
console.log(name, score);
// const third = pair[2];
//   TS2493: Tuple type 'Pair' of length '2' has no element at index '2'.

// ---- as const ----
const point = [3, 4] as const; // readonly [3, 4]: a readonly tuple of literal types
// point[0] = 5;
//   TS2540: Cannot assign to '0' because it is a read-only property.
console.log(point);
