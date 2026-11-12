// ---- Function Type Expressions ----
function greeter(fn: (a: string) => void) {
  fn("Hello, World");
}
function printToConsole(s: string) {
  console.log(s);
}
greeter(printToConsole);
// generic are used when we want to describe a correspondence between two values.
// We do this by declaring a type parameter in the function singnature.
function firstElement<Type>(arr: Type[]): Type | undefined {
  return arr[0];
}
// s is of type 'string'
const s = firstElement(["a", "b", "c"]);
// n is of type 'number'
const n = firstElement([1, 2, 3]);
// u is of type undefined
const u = firstElement([]);
// ---- Inference ----
function map<Input, Output>(arr: Input[], func: (arg: Input) => Output): Output[] {
  return arr.map(func);
}

// Parameter 'n' is of type 'string'
// 'parsed' is of type 'number[]'
const parsed = map(["1", "2", "3"], (n) => parseInt(n));
// ---- Constraints ----
// Sometimes we want to relate two values, but can only operate on a certain subset of values.
// Constraints are used to limit the kinds of types that a type parameter can accept
function longest<Type extends { length: number }>(a: Type, b: Type) {
  if (a.length >= b.length) {
    return a;
  } else {
    return b;
  }
}
 
// longerArray is of type 'number[]'
const longerArray = longest([1, 2], [1, 2, 3]);
// longerString is of type 'alice' | 'bob'
const longerString = longest("alice", "bob");
// Error! Numbers don't have a 'length' property
// const notOK = longest(10, 100); TS2345: Argument of type 'number' is not assignable to parameter of type '{ length: number; }'.
function identity<T>(arg: T): T {return arg;};
identity("x")
const myId: <T>(arg: T) => T = identity;
interface GenericIdentityFn<T>
{
  (arg: T) : T
};
const idNum: GenericIdentityFn<number> = identity;

class Box<T> {
  constructor(public contents: T) {}
};
new Box(42).contents

function loggingIdentity<T extends {length: number}>(arg: T): T{
  console.log(arg.length);
  return arg;
}
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K]{
  return obj[key];
}
