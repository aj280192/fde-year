//let obj: any = { x: 0} // TS6133: variable is declared but its value is never read.
// ---- Type Annotation on Variables ----
const obj: string = "hello";
let myName: string = "Ajay"; // type is mostly infered on variables based on it's assigned value
console.log(obj);
// ---- Functions ----
// Parameter type annotation
function greet(name: string) {
  console.log("Hello, " + name.toUpperCase() + "!!");
}
greet(myName);
// Return type annotation -> we dont have to annotate return type it is infered like how it is done for variables
function getFavoriteNumber(): number {
  return 26;
}
console.log(getFavoriteNumber());
// Function which return Promises
async function getFavoriteNumberP(): Promise<number> {
  return 26;
}
console.log(getFavoriteNumberP);
// ---- Anonymous Functions ----
const names = ["Alice", "Bob", "Eve"];
 
// Contextual typing for function - parameter s inferred to have type string
names.forEach(function (s) {
  console.log(s.toUpperCase());
});
 
// Contextual typing also applies to arrow functions
names.forEach((s) => {
  console.log(s.toUpperCase());
});
// Parameters of anonymous functions are automatically given types, the process is calld contextual typing
// ---- Object Types ----
// The parameter's type annotation is an object type
function printCoord(pt: { x: number; y: number }) {
  console.log("The coordinate's x value is " + pt.x);
  console.log("The coordinate's y value is " + pt.y);
}
printCoord({ x: 3, y: 7 });
// We simply list object properties and their types.
// Optional Properties -> Object can specify some or all of its properties are optional. 
function printName(obj: { first: string; last?: string }) {
  console.log("First name: " + obj.first + " Last name: ")
  if (obj.last !== undefined) {
    console.log("Last name: " + obj.last)
  }
}
// Both OK
printName({ first: "Bob" });
printName({ first: "Alice", last: "Alisson" });
// ---- Union Types ----
function printId(id: number | string) {
  console.log("Your ID is: " + id);
}
// OK
printId(101);
// OK
printId("202");
// Error
// printId({ myID: 22342 }); TS2345: Argument of type '{ myID: number; }' is not assignable to parameter of type 'string | number'.

// Union will not allow an opertion that is not valid on every member of the union.
// function printId(id: number | string) {
//   console.log(id.toUpperCase()); 
// }
// TS2339: Property 'toUpperCase' does not exist on type 'string | number'. Property 'toUpperCase' does not exist on type 'number'.
// We can try narrowing with code
function printIdN(id: number | string) {
  if (typeof id === "string") {
    // In this branch, id is of type 'string'
    console.log(id.toUpperCase());
  } else {
    // Here, id is of type 'number'
    console.log(id);
  }
}
printIdN(101);
printIdN("202");
// Another example
function welcomePeople(x: string[] | string) {
  if (Array.isArray(x)) {
    // Here: 'x' is 'string[]'
    console.log("Hello, " + x.join(" and "));
  } else {
    // Here: 'x' is 'string'
    console.log("Welcome lone traveler " + x);
  }
}
welcomePeople(myName);
welcomePeople(names);
// If common property exists we can use it without narrowing
// Return type is inferred as number[] | string
function getFirstThree(x: number[] | string) {
  return x.slice(0, 3);
}
console.log(getFirstThree("123"));
// ---- Type Aliases ----
type Point = {
  x: number;
  y: number;
};
 
// Exactly the same as the earlier example
function printCoordA(pt: Point) {
  console.log("The coordinate's x value is " + pt.x);
  console.log("The coordinate's y value is " + pt.y);
}
 
printCoordA({ x: 100, y: 100 });

// ---- Interfaces ----
// It is another way to name an object type.
interface PointI {
  x: number;
  y: number;
}
 
function printCoordI(pt: PointI) {
  console.log("The coordinate's x value is " + pt.x);
  console.log("The coordinate's y value is " + pt.y);
}
 
printCoordI({ x: 100, y: 100 });

// ---- Type Assertions ----
// const myCanvas = document.getElementById("main_canvas") as HTMLCanvasElement;

// const x = "hello" as number; TS2352 Conversion of type 'string' to type 'number' may be a mistake because neither type sufficiently overlaps with the other. If this was intentional, convert the expression to 'unknown' first.

// ---- Literal Types ----
let changingStringL = "Hello World";
changingStringL = "Olá Mundo";
// Because `changingString` can represent any possible string, that
// is how TypeScript describes it in the type system
changingStringL;
       
const constantStringC = "Hello World";
// Because `constantString` can only represent 1 possible string, it
// has a literal type representation
constantStringC;

// combining literals with union
function printText(s: string, alignment: "left" | "right" | "center") {
  // ...
}
printText("Hello, world", "left");
// printText("G'day, mate", "centre"); TS2345: Argument of type '"centre"' is not assignable to parameter of type '"left" | "right" | "center"'.
// ---- Null and Undefined ----
// Always do a strict null check
function doSomething(x: string | null) {
  if (x === null) {
    // do nothing
  } else {
    console.log("Hello, " + x.toUpperCase());
  }
}
// Value isn't null or undefined -> !
function liveDangerously(x?: number | null) {
  // No error
  console.log(x!.toFixed());
}
