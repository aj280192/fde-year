# Week 2 · 12 to 18 October 2026 · Production Python

## Weekly note

### What I built

A small Python library, `toolkit`, that validates the messages an AI agent exchanges with its tools: tool definitions, tool calls and tool results. It ships with a command, `toolkit validate calls.json`, that checks a file of tool calls, prints a report, logs each run as JSON and exits with 0, 1 or 2. It is strictly typed, tested, installable from a wheel and tagged `toolkit-v0.1.0`. The agent loop in week 9 will reuse these models.

### What broke

- My first tests built invalid objects by calling the model constructors directly. Pyright strict flagged every one as a bug. The fix was to feed invalid JSON through `model_validate_json`, which is also how an agent really receives tool calls. Pyright checks the code I write; Pydantic checks the data that arrives. They are two different safety nets.
- I used Pydantic 1 syntax, `Field(env=...)`, in my settings. Pydantic 2 ignores it with only a deprecation warning, so the setting looked configured but was read only because of the prefix.
- I missed Tuesday and Wednesday and compressed three sessions into the weekend.

### What I would tell a customer

This toolkit check every tool call your agent makes before it runs, and make the error say which field is wrong and what was expected. The model reads that error and fixes its next attempt, so a precise error is worth more than a retry.

### My checklist: production-grade Python

| Item | What it means in my code | Why a customer's platform team cares |
| --- | --- | --- |
| Typing | Pyright in strict mode passes with 0 errors and no `type: ignore` | Wrong types are caught before deployment, and the code is safer to change |
| Configuration | `Settings` reads `TOOLKIT_` environment variables and fails at start-up if `TOOLKIT_ENV` is missing or invalid | One build runs in dev and prod; a bad setting fails in the first second, not on the first real request |
| Logging | One JSON line per event on standard error, with `request_id` and `duration_ms`; no secrets or prompts | Logs can be searched and filtered in Splunk; customer data stays out of them |
| Errors | `AppError` with a stable `code` and four subclasses; exit codes 0, 1 and 2 | Callers react by type: retry a timeout, never retry bad input; pipelines can tell bad data from a broken tool |
| Packaging | A `src/` layout, `py.typed`, a console script, a wheel that installs and runs in a clean environment | They install a versioned artefact, not a folder of scripts |
| Tests | [13] tests, covering every invalid payload and every exit code | Behaviour is pinned down, so changes that break it fail in CI |

### What is next

Week 3 is async, streaming and failure handling. The error codes from this week decide what gets retried.
---

## Mon 12 Oct · AI Engineering ch. 2, foundation models

### Five lines

- New: Top-k limits each sampling step to the k most likely next tokens, then samples among them.
- New: Top-p (nucleus sampling) limits each step to the smallest set of next tokens whose probabilities add up to p. It adapts: few candidates when the model is confident, many when it is unsure.
- Changes how I would build: Temperature, top-k and top-p are settings I would choose per task and record with every request, so outputs can be reproduced and explained to a customer.
- Changes how I would build: Providers now offer native structured output, which is constrained decoding run on their side. I would check what each provider supports before writing my own parsing and retry logic.
- Question: Can forcing a format cause hallucination? For example, if a schema makes a field required and the source has no value for it, does the model invent one? Does adding an "unknown" option fix that?

### Temperature experiment

Model: Gemma 4, through Ollama
Prompt: Suggest one name for a coffee shop. Reply with the name only.

| Temperature | Distinct answers out of 5 | What I noticed |
| --- | --- | --- |
| 0 | 1 | Temperature 0 is greedy decoding: it always takes the most likely token, so the same prompt gives the same output. |
| 1 | 1 | Temperature 1 samples from the model's unchanged probabilities. Five identical answers means the model is very confident on this prompt. A more open prompt would show variation. |
| 2 | 4 | Temperature 2 flattens the distribution, so less likely tokens get picked more often. More varied, but also more likely to be odd or wrong. |

### Three ways to get structured output

| Method | How it works, in one line | One cost |
| --- | --- | --- |
| Prompting for the format | Instructs the model to answer in the format and hopes it complies | No guarantee: some outputs come back invalid, and the code must handle that |
| Validation with retry | Checks the output against a schema in code and asks again if it fails | Each retry is a full extra call, adding latency and token cost, and it can still fail after the last retry |
| Constrained decoding | At each step, blocks any token that would break the schema or grammar. Like top-k, it filters the candidate tokens, but by validity instead of rank | Needs control of the decoder (vLLM, or a provider's structured-output feature), supports only some schemas, and a tight schema can lower answer quality |

### Where it applies at work

For NLP-to-SPL, a generated query has to be valid and repeatable, so I would use a low temperature by default. Two options worth testing: sample several candidates at a higher temperature and keep the first that passes a syntax check, or constrain decoding to the query grammar.

---

## Tue 13 Oct · Fluent Python ch. 8 and 15, type hints

### Cheat sheet

| Choice | Use the first when | Use the second when |
| --- | --- | --- |
| `Protocol` or abstract base class | When you want structural "duck typing". Use it to verify an object has the right methods/attributes without forcing explicit subclassing (great for third-party plug-ins or loose interfaces). | When you want explicit class inheritance. Use it to share core code/default logic among subclasses and enforce strict implementation boundaries at runtime. |
| `TypedDict`, dataclass or Pydantic model | When you are working with pure JSON-like dictionaries (like raw API payloads or database rows) and want key-name autocompletion without the overhead of creating a class instance. | When you need a true data object with behavior. Use a Dataclass for clean OOP models with custom methods. Use a Pydantic Model when you need runtime data validation, coercion, and parsing (like FastAPI endpoints). |
| `object` or `Any` | When a value can literally be anything, but you still want strict type-safety. The type checker forces you to perform explicit type checks (isinstance()) before you can call methods on it. | When you want to turn off the type checker entirely for that variable. It allows you to call any method or access any attribute without a single warning (use sparingly as a last resort). |

### Pyright strict on the baseline API

- Errors at the start: Partiable annotated arguments, return type missing, dict or list without type arguments.
- Errors at the end: All fixed.
- The fix that taught me most: How typing should be done for global arguments.

---

## Wed to Sat · Labs

The code and its notes live in the lab folders. Link them here.

- Wed 14 Oct, tool-call models in Pydantic: [labs/week02/](../labs/week02/)
- Thu 15 Oct, logging, settings and errors:
- Sat 17 Oct, library with a CLI, tagged v0.1.0:

Friday's two-pointer problems go in `notes/reps.csv`, not here.