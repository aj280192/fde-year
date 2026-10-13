# Week 2 · 12 to 18 October 2026 · Production Python

## Weekly note

Written Sunday 18 October. 300 to 500 words.

### What I built

### What broke

### What I would tell a customer

### My checklist: production-grade Python

| Item | What it means in my code | Why a customer's platform team cares |
| --- | --- | --- |
| Typing | | |
| Configuration | | |
| Logging | | |
| Errors | | |
| Packaging | | |
| Tests | | |

### What is next

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
| `Protocol` or abstract base class | | |
| `TypedDict`, dataclass or Pydantic model | | |
| `object` or `Any` | | |

### Pyright strict on the baseline API

- Errors at the start:
- Errors at the end:
- The fix that taught me most:

---

## Wed to Sat · Labs

The code and its notes live in the lab folders. Link them here.

- Wed 14 Oct, tool-call models in Pydantic: [labs/week02/](../labs/week02/)
- Thu 15 Oct, logging, settings and errors:
- Sat 17 Oct, library with a CLI, tagged v0.1.0:

Friday's two-pointer problems go in `notes/reps.csv`, not here.