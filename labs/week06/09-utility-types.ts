type TaskState = "queued" | "running" | "waiting_for_input" | "succeeded" | "failed" | "cancelled";
interface Task {
  id: string;
  state: TaskState;
  input: string;
  result: string | null;
  created_at: string;
  updated_at: string;
}
type TaskPatch = Partial<Task>;
type Options = {retries?: number; timeout?: number};
type Resolved = Required<Options>;
const t: Readonly<Task> = {id: "t_1",
  state: "queued", 
  input: "Why is the pod down?",
  result: null,
  created_at: "040900:2026/11/12",
  updated_at: "041100:2026/11/12"};

// t.state = "running"; // TS2540: Cannot assign to 'state' because it is a read-only property.
type TaskSummary = Pick<Task, "id" | "state">;
// type bad = Pick<Task, "idd"> // error: "idd" isn't a key of Task

type NewTask = Omit<Task, "id" | "created_at" | "updated_at">;
// { state: TaskState; input: string; result: string | null }

type Record<K extends keyof any, T> = { [P in K]: T };

const countsByState: Record<TaskState, number> = {
  queued: 0, running: 2, waiting_for_input: 0,
  succeeded: 10, failed: 1, cancelled: 3,
};

type Final = "succeeded" | "failed" | "cancelled";
type Active = Exclude<TaskState, Final>;
// "queued"            extends Final? no  → "queued"
// "running"           extends Final? no  → "running"
// "waiting_for_input" extends Final? no  → "waiting_for_input"
// "succeeded"         extends Final? yes → never   (never disappears from a union)
// …
// result: "queued" | "running" | "waiting_for_input"

type FinalStates = Extract<TaskState, Final>;         // "succeeded" | "failed" | "cancelled"
type Result = NonNullable<Task["result"]>;            // string

function makeTask(input: string, state: TaskState = "queued") {
  return { id: "t_1", input, state, result: null as string | null };
}
type Made = ReturnType<typeof makeTask>;    // { id: string; input: string; state: TaskState; result: string | null }
type Args = Parameters<typeof makeTask>;    // [input: string, state?: TaskState]

// async function fetchTask(): Promise<Task> { ... };
// type Fetched = Awaited<ReturnType<typeof fetchTask>>;   // Task