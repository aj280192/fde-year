// ---- Function Type Expression ----
function greeter(fn: (a: string) => void){
    fn("Hello, World");
}

function printToConsole(s: string) {
    console.log(s);
}

greeter(printToConsole);

type GreetFunction = (a: string) => void;
function greeteralias(fn: GreetFunction){
    fn("Hello, World");
}

// ---- Call Signatures ----
type DescribableFuntion = {
    description: string;
    (someArg: number): boolean;
}

function doSomething(fn: DescribableFuntion) {
    console.log(fn.description + " returned " + fn(6));
}

function myFunc(someArg: number){
    return someArg > 3;
}

myFunc.description = "default description";
doSomething(myFunc);

// ---- Construct Signatures ----
// type SomeConstructor = {
//     new (s: string): SomeObject;
// };

// function fn(ctor: SomeConstructor){
//     return new ctor("hello");
// }
interface CallOrConstruct{
    (n?: number): string;
    new (s: string): Date;
}

function fn(ctor: CallOrConstruct){
    console.log(ctor(10));
    console.log(new ctor("10"));
}

fn(Date);
