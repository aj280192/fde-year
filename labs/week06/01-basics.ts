  const user = { name: "Ajay", age: 30 };
  // user.location;                  // TS2339: Property 'location' does not exist
  const announcement = "Hello";
  // announcement.toLocaleLowercase(); // TS2551: did you mean 'toLocaleLowerCase'?
//   if (Math.random < 0.5) {}        // TS2365: a function compared with a number (missing ())

// This is an industrial-grade general-purpose greeter function:
// function greet(person, date) { // TS7006: Parameter implicitly has 'any' type
//   console.log(`Hello ${person}, today is ${date}!`);
// }
 
// greet("Brendan"); // TS2554: An agrument is not provided

  function greet(person: string, date: Date): string {
    return `Hello ${person}, today is ${date.toDateString()}!`;
  }
  // greet("Maddison", Date());  // TS2345: Date() returns a string; you meant new Date()