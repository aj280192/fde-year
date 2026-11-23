# Architecture Patterns with Python · ch. 1 to 4

Harry Percival and Bob Gregory, *Architecture Patterns with Python* (O'Reilly, 2020), also free at
[cosmicpython.com](https://www.cosmicpython.com/book/preface.html). Skimmed Mon 23 Nov 2026, week 8.

**Why now:** these four chapters are the theory behind the refactor I did in week 4, when the task
API went from routes reading dicts to four layers. Chapter 3, on fakes over mocks, matters most this
week: on Wed 25 Nov I test an agent loop with a fake model.

**How to read this note:** each chapter has what the book says, then how my task API
(`labs/week05`) matches it or differs. The four questions from the plan are answered at the end.

---

## Five lines

1. **Ch. 1, domain model:** the business rules live in plain Python with no frameworks, written in
   the business's own words, and tested in those words.
2. **Ch. 2, repository:** storage sits behind a small collection-like interface (`add`, `get`), so
   the domain doesn't know the database exists and tests can use a fake.
3. **Ch. 3, coupling and abstractions:** separate deciding *what* to do from *doing* it, inject the
   messy dependencies, and test with fakes that check the end state, not mocks that check calls.
4. **Ch. 4, service layer:** each use case is one function that fetches, checks, calls the domain
   and saves; the web routes become thin adapters, and most tests run against the services.
5. **The common idea:** dependency inversion. High-level policy (the rules, the use cases) depends
   on abstractions, and the details (Postgres, HTTP) depend on them too, never the other way round.

---

## Ch. 1 · Domain modelling

### What the book says
- **The domain** is the problem the business solves; **the model** is a simplified map of it. The
  domain model is the code that holds the business rules, named in the business's language (the
  *ubiquitous language* of domain-driven design).
- **Value objects** are defined only by their data: two with the same data are interchangeable, so
  they are usually immutable. A frozen dataclass gives value equality for free.
- **Entities** keep an identity while their attributes change. Equality should follow that
  identity, and `__eq__` and `__hash__` must agree.
- **Domain services:** an operation that belongs to no single object can be a plain function.
  Not everything needs a class called `Manager` or `Factory`.
- **Domain exceptions** name business situations (`OutOfStock`), so the code reads in business terms.
- **Tests come first** and are named after behaviour, in business words, so a non-engineer could read
  them.
- A domain service models a **business process**; a service-layer function models an
  **application use case**. Ch. 4 builds the second.

### My design against it
| Book idea | In my code | Same or different |
| --- | --- | --- |
| Rules in plain Python, no frameworks | `domain/task.py`: `TaskState`, `ALLOWED`, `TERMINAL`, `can_transition`, `Task.cancel`, `Task.retry`; `domain/idempotency.py`: `fingerprint`, `TTL` | same; `test_architecture.py` enforces that `domain/` imports nothing from `api/` or `db/` |
| Value objects | `TaskError`, `IdempotencyRecord`, and in `/v1/ask` `Citation` and `Source`: all frozen dataclasses | same |
| Entities with identity | `Task`, identified by `id` | **different:** my `Task` is a *frozen* dataclass, so a change returns a new copy (`replace(...)`), and equality compares every field, not just the id. Immutable entities suit my design because the repository's `save` replaces the whole task, but two versions of the same task are "not equal", which the book would avoid |
| Domain services as functions | `fingerprint(input)`, `can_transition(old, new)` | same |
| Domain exceptions | `TaskNotFound`, `TaskAlreadyFinished`, `TaskNotFailed`, `IdempotencyKeyReused` in `domain/errors.py`, with no HTTP codes | same; `api/errors.py` is the only place that turns them into 404 or 409 |
| Tests named after behaviour | `test_cancel_twice_returns_the_same_task`, `test_retry_task_that_did_not_fail_is_409` | mostly same; the API tests mix in HTTP words such as "409" |
| Ubiquitous language | task, queued, waiting for input, cancel, retry | same: the words in DESIGN.md, the code and the tests match |

---

## Ch. 2 · The repository pattern

### What the book says
- **Dependency inversion for storage:** the ORM should depend on the model, not the model on the
  ORM. The book maps plain classes to tables from outside ("classical mapping"), so the model never
  imports SQLAlchemy.
- **A repository** makes storage feel like an in-memory collection. The simplest has two methods,
  `add` and `get`. In Python, duck typing can stand in for a formal abstract class.
- **A fake repository** can be a thin wrapper round a set. If an abstraction is hard to fake, it is
  probably too complicated.
- **Ports and adapters:** the interface the application depends on is the *port*; each
  implementation behind it is an *adapter*.
- **Trade-off:** the pattern pays off for complex domains. A simple create-read-update-delete app
  doesn't need it, and every extra layer is more to learn and maintain.

### My design against it
| Book idea | In my code | Same or different |
| --- | --- | --- |
| Model free of the ORM | domain `Task` is a plain dataclass; `db/models.py` has a separate `TaskRow`; `db/repository.py` converts between them | same goal, **different route:** explicit converter functions instead of classical mapping. More code to keep in step, but no SQLAlchemy magic on my domain objects |
| Port | the `TaskRepository` protocol in `repository.py` | same; a `Protocol` is checked duck typing, so pyright confirms each adapter fits |
| Adapters | `InMemoryTaskRepository`, `PostgresTaskRepository` | same, with two real adapters |
| Two methods, `add` and `get` | six: `add`, `get`, `save`, `list_for_owner`, `get_idempotency`, `put_idempotency` | **different:** see question 2 below for why each exists |
| Ownership | `get(task_id, owner)` returns `None` for another key's task | **my addition:** the repository enforces isolation, so no service can forget the owner check |
| Fake for tests | `InMemoryTaskRepository` | same, and **stronger:** the `repo` fixture in `conftest.py` runs every repository and service test on both the fake and Postgres. That proves the fake behaves like the real thing, which the book doesn't do in these chapters |
| Is it worth it here? | a state machine, idempotency, ownership, pagination, and agents coming in Phase 2 | yes; for plain CRUD it would be too much |

---

## Ch. 3 · Coupling and abstractions

### What the book says
- **Coupling** is fine inside one cohesive unit and harmful between unrelated parts; unmanaged, it
  becomes a "Big Ball of Mud" where every change is risky.
- **The example**, syncing two folders: the first version mixes file-system calls with decisions,
  so its tests need real directories and it can't grow a dry-run mode.
- **Functional core, imperative shell** (Gary Bernhardt): read the state (I/O), decide what to do in
  a pure function that returns a plan of actions, then carry the plan out (I/O). The pure core is
  tested with plain dictionaries.
- **Choosing the abstraction:** split by responsibility (look at the state, decide, act), and keep
  the *what* (the planned actions) apart from the *how* (the file operations).
- **Dependency injection:** pass the dependency in, with the real one as the default. Tests pass a
  fake that keeps state in memory and records what it was asked to do.
- **Why not `mock.patch`:** patching makes code testable without improving its design (it gives no
  dry-run mode); mock-heavy tests are tied to implementation details and break on refactors; and
  they make the test suite hard to read. Designing for testability is designing for extensibility.
- **Mocks against fakes:** mocks check *how* collaborators were called (London-school TDD); fakes
  are working stand-ins, and tests check the *end state* (classic TDD). The book takes the classic
  side, while saying the other school isn't wrong.
- **Heuristics:** model messy state as familiar data structures; separate what from how; find the
  seams where an abstraction fits; make implicit concepts explicit.

### My design against it
| Book idea | In my code | Same or different |
| --- | --- | --- |
| Functional core | `Task.cancel` and `Task.retry` are pure: they take a task and a time and return a new task or raise | same |
| Imperative shell | services do the I/O around the core: `get`, call the rule, `save` or `add` | same |
| Inject time and randomness | services take `now` and `new_id` as arguments; `create_app` takes `now=`; tests pass a `FakeClock` | same, and the reason `test_cancel_twice_returns_the_same_task` can check `updated_at` exactly |
| Inject the dependency, real one by default | `create_app(keys, now=..., repo=..., answerer=...)`; `repo` defaults to the in-memory one | same |
| Fakes over mocks | `InMemoryTaskRepository`, `FakeClock`, and the fake answerers in `test_ask.py` (`answers`, `abstains`, `breaks`) | same: tests check the stored state or the events sent, not which methods were called |
| Make implicit concepts explicit | `Created(task, replayed)` and `Page(tasks, next_cursor)` instead of loose tuples | same |
| A gap the book would point at | `serve.py`'s adapter built the `AskResult` inline, with no seam, so no test covered it, and the `sorted()` bug got through | **different, and a lesson:** pull it into a `to_ask_result(answer)` function and test it with a fake `Answer` |

---

## Ch. 4 · The service layer

### What the book says
- **Why:** as the Flask app grew, its routes took on orchestration: loading, checking input against
  stored state, handling errors, committing. None of that is specific to the web, so it moves into a
  service layer (also called the use-case or orchestration layer).
- **A typical service:** fetch from the repository, check the request against the current state,
  call the domain, save if everything succeeded.
- **Commit:** the book passes a session and uses a fake one that records whether `commit` was
  called, as a stopgap until the Unit of Work pattern in ch. 6.
- **Testing:** keep a few end-to-end tests for web behaviour (status codes, JSON, the happy and the
  unhappy path), and move the rest to fast service tests against the fake repository. The test
  pyramid should be mostly fast tests at the bottom.
- **Depend on abstractions:** the service's repository parameter is typed as the abstract class, so
  tests pass a fake and production passes the real one.
- **Folders by role:** domain, service layer, adapters, entrypoints (Flask, a command line), and
  tests split into unit, integration and end-to-end.
- **Trade-off:** one place lists every use case and the domain can be refactored freely, but it is
  another layer, and putting too much logic in services leaves an *anemic domain model*. Add it once
  orchestration starts piling up in the routes.
- **Left open at the end of ch. 4:** the services still depend on domain objects in their
  arguments, and on the session.

### My design against it
| Book idea | In my code | Same or different |
| --- | --- | --- |
| Services do fetch, check, call the domain, save | `cancel_task`: `get_task`, `task.cancel(now)`, `repo.save` if it changed; `retry_task`: `get_task`, `task.retry(...)`, `repo.add` | same |
| Thin routes | each route in `create_app` is a few lines: check the scope, call one service, convert to `TaskOut` | same |
| Services take primitives | `owner: str`, `task_id: str`, `input: str`, `now: datetime` | **ahead of ch. 4:** the coupling the book leaves open (domain objects as arguments) I never had |
| Services return domain objects, raise domain errors | `Task`, `Created`, `Page`; `TaskNotFound`, `TaskNotFailed` | same; HTTP lives only in `api/` |
| Depend on the abstraction | `repo: TaskRepository`, the protocol | same |
| Commit and transactions | no session: each repository method is its own transaction | **different, and a known gap:** a service's read and write happen in two transactions. That is the cancel-versus-success race in DESIGN.md §14 row 6. The book's answer is the Unit of Work (ch. 6) or a conditional `UPDATE` |
| Test pyramid, mostly service tests | about 20 service tests against 57 or so API tests | **inverted:** I test more through HTTP than the book would. The API tests are fast because the store is in memory, but they repeat checks the service tests could do more simply |
| Folders by role | `domain/`, `api/` (the entrypoint), `db/` (an adapter), with `services.py` and `repository.py` at the top | similar idea, flatter layout; tests aren't split into unit, integration and end-to-end |
| Anemic-domain risk | rules sit on `Task` (`cancel`, `retry`), not in services | avoided so far; idempotency is the exception, with its logic in `create_task` rather than the domain |

---

## The four questions

### 1 · Domain modelling: what in my code is a domain rule, and what is plumbing?
**Domain rules** (`domain/`), true whatever the delivery mechanism:
- the six states, which moves between them are allowed, and which states are final
- cancelling twice changes nothing; a finished task can't be cancelled
- only a failed task can be retried, and retrying makes a new task
- an idempotency key replays the same task for the same input within 24 hours, and refuses a
  different input

**Plumbing**, which would change if the API became a command-line tool or a queue consumer:
- status codes and the error shape (`api/errors.py`)
- API keys and scopes (`api/auth.py`)
- page tokens (`api/pagination.py`)
- SQL rows and their converters (`db/`)
- server-sent events and `serve.py`

**My test for telling them apart:** would the sentence still be true in a command-line version?
"A failed task can't be cancelled": yes, domain. "That returns 409": no, plumbing.

### 2 · Repository: which methods does it need, and why nothing more?
Each method exists because a service needs it:

| Method | Needed by | Why |
| --- | --- | --- |
| `add(task, owner)` | `create_task`, `retry_task` | store a new task with its owner, kept out of `Task` itself |
| `get(task_id, owner)` | `get_task`, so every get, cancel and retry | fetch one task, and return nothing for another key's, so the 404 can't leak |
| `save(task)` | `cancel_task` | replace a changed task; separate from `add` so a bug can't silently create one |
| `list_for_owner(owner, before, limit)` | `list_tasks` | the newest-first page after a cursor; the service asks for one extra to know if there's another page |
| `get_idempotency`, `put_idempotency` | `create_task` | remember what an idempotent create produced |

Nothing more, because no service needs anything else: no delete (a task is a record of work, and
cancel covers "stop this"), no update of single fields, no search. **One thing I'd change:** the two
idempotency methods are a second concern in the same interface. A separate `IdempotencyStore` port
would keep each interface to one job, at the cost of one more fake.

### 3 · Coupling: which modules would have broken if I'd swapped the dicts for Postgres before the refactor?
Before the refactor the routes read and wrote the dicts directly, so **every route** would have
changed, the **paging and idempotency logic inside them** would have been rewritten in SQL, and
**every test** would have needed a database. After the refactor, swapping storage added one file,
`db/repository.py`, and changed nothing above it. DESIGN.md records it: every HTTP test passed with
only import and setup changes.

**Ch. 3 in one sentence:** depend on the protocol, not the dict or Postgres, and test with a fake;
my `repo` fixture then proves the fake and Postgres behave the same, which a mock never could.

### 4 · Service layer: what does a service take in, and what does it return?
**In:** the repository (typed as the protocol), the owner's key id, plain values (the task id, the
input, the idempotency key), and the dependencies that would make tests flaky, the time (`now`) and
the id generator (`new_id`).

**Out:** domain objects (`Task`, `Created`, `Page`), never an HTTP response. On failure it raises a
domain error, and `api/errors.py` turns that into an HTTP error.

**So:** a service is one use case. `retry_task` is four lines because the rule lives on `Task`.

---

## What I'll change, and when

| Change | Book idea | When |
| --- | --- | --- |
| Pull `serve.py`'s conversion into `to_ask_result()` and test it with a fake `Answer` | ch. 3: find the seam, test the core | Tue 24 Nov, pytest day |
| Move checks that don't need HTTP from `test_api.py` to `test_services.py` | ch. 4: the test pyramid | Tue 24 Nov, if time allows |
| Fix the read-then-write race with a conditional `UPDATE` or a Unit of Work | ch. 4's open question, answered in ch. 6 | before a worker exists (Phase 2) |
| Split idempotency into its own port | ch. 2: a small interface per job | only if a second store needs it |

## What I'll use on Wednesday

The agent loop's model is a dependency, like the repository: `run(task, tools, model, max_steps)`
takes it as an argument. The `FakeModel` is a **fake, not a mock**: it returns scripted replies, and
the tests check what the loop ends with (an answer on step 2, `stopped_reason='step_limit'`, two tool
results matched by id), not which methods it called. The loop itself is an imperative shell round a
small decision: read the reply, then answer, call tools or stop.

## Questions I still have

1. When should an entity be frozen, as my `Task` is, and when mutable, as the book's are? Is
   replacing the whole task on every change a problem at scale?
2. Ch. 4 ends with the services still depending on the session. Should my repository methods stay
   one transaction each, or move to a Unit of Work before Phase 2's worker?

## In an interview, in one sentence each

- **Why a repository?** It puts storage behind a small interface, so the business rules never know
  the database exists, and tests run on an in-memory fake that the same test suite proves behaves
  like Postgres.
- **Fakes or mocks?** Fakes: a working stand-in lets the test check the end state, so it survives
  refactoring, while a mock checks how methods were called and breaks when the implementation changes.
- **What goes in a service?** One use case: fetch, check against the current state, call the domain
  rule, save. No HTTP and no SQL.