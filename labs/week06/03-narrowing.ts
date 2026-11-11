// function padLeft(padding: number | string, input: string): string {
//   return " ".repeat(padding) + input; TS2345: Argument of type 'string | number' is not assignable to parameter of type 'number'. Type 'string' is not assignable to type 'number'.
// }
function padLeft(padding: number | string, input: string): string {
  if (typeof padding === "number") {
    return " ".repeat(padding) + input;
  }
  return padding + input;
}
// The process of refining types to more specific types than declared is called narrowing.

// function printAll(strs: string | string[] | null) {
//   if (typeof strs === "object") {
//     for (const s of strs) { TS18047: 'strs' is possibly 'null'.
//       console.log(s);
//     }
//   } else if (typeof strs === "string") {
//     console.log(strs);
//   } else {
//     // do nothing
//   }
// }

// In JavaScript "null" -> object
function printAll(strs: string | string[] | null) {
  if (strs && typeof strs === "object") {
    for (const s of strs) {
      console.log(s);
    }
  } else if (typeof strs === "string") {
    console.log(strs);
  }
}
printAll("Hello");
// ---- Equality Narrowing ----
function example(x: string | number, y: string | boolean) {
  if (x === y) {
    // We can now call any 'string' method on 'x' or 'y'.
    x.toUpperCase();
    y.toLowerCase();
  } else {
    console.log(x);
    console.log(y);
  }
}
example(2, "Hello");
// ---- in operator narrowing ----
type Fish = { swim: () => void };
type Bird = { fly: () => void };
type Human = { swim?: () => void; fly?: () => void };
 
function move(animal: Fish | Bird | Human) {
  if ("swim" in animal) {
    animal; // (parameter) animal: Fish | Human
  } else {
    animal; // (parameter) animal: Bird | Human
  }
}
// ---- instanceof narrowing ----
function logValue(x: Date | string) {
  if (x instanceof Date) {
    console.log(x.toUTCString()); // (parameter) x: Date
  } else {
    console.log(x.toUpperCase()); // (parameter) x: string
  }
}

// ---- Assignments ----
let x = Math.random() < 0.5 ? 10 : "hello world!"; // let x: string | number
x = 1;
console.log(x); // let x: number
x = "goodbye!";
console.log(x); // let x: string

// ---- Type predicate ----
function isFish(p: Fish | Bird): p is Fish {
  return (p as Fish).swim !== undefined;
}

// ---- Discriminated Unions ----
type Shape =
  | { kind: "circle"; radius: number }
  | { kind: "triangle"; base: number; height: number }
  | { kind: "square"; side: number };

function area(s: Shape): number {
  switch (s.kind) {
    case "circle": return Math.PI * s.radius ** 2;   // s is the circle shape
    case "square": return s.side ** 2;     
    case "triangle": return 1/2 * s.base * s.height          // s is the square shape
  }
}