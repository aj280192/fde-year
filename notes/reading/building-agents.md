# Building agents · Anthropic and OpenAI guides

Read Thu 19 Nov 2026, week 7, about 60 minutes.

- Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
  (December 2024).
- OpenAI, [A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf).

**Why now:** the agent loop I write on Wed 25 Nov, and the controls I add on Wed 2 Dec, start from these
two documents. Both say the same thing first: start simple, and earn every extra layer.

---

## Five lines

1. **Workflows follow a path I wrote in code; agents choose their own path.** In a workflow, the model
   and the tools are orchestrated through predefined steps. In an agent, the model decides what to do
   next, which tool to call, and when it is finished. Agents trade latency and cost for flexibility.
2. **The five workflow patterns** (Anthropic) are prompt chaining, routing, parallelisation,
   orchestrator-workers and evaluator-optimiser. Each is a fixed shape I can test before I let a model
   steer.
3. **I would refuse to build an agent** when I can write the steps down in advance, when one prompt with
   retrieval already meets my evaluation target, or when I cannot check the outcome of its actions. A
   workflow is cheaper, faster and easier to debug, and I earn the agent only when the problem cannot be
   predefined.
4. **The guardrail my loop will need is tool safeguards (OpenAI):** rate every tool low, medium or high
   risk by write access, reversibility and impact, and make a high-risk call stop for a human. For the
   operations agent, `restart_pod` is high risk and `read_logs` is low.
5. **Question I still have:** OpenAI says to split an agent when its tools overlap or its prompt has many
   nested branches, but how do I measure "too similar" before I split? Is tool-selection accuracy on my
   scenario set the signal?

---

## What I believed before reading, and what the guides say

| My belief | Anthropic | OpenAI | Verdict |
| --- | --- | --- | --- |
| Start with a plain prompt, add evaluation, move to an agent, and only then maybe several agents | find the simplest solution and add complexity only when needed; often one well-built call with retrieval and examples is enough | build one agent first, add tools gradually, and move to several agents only when needed | agree |
| Simple designs often achieve more | the first principle for agents is to keep the design simple | do not start with a fully autonomous, complex agent | agree |
| Three things matter: simplicity, transparency, and documenting and testing | exactly these three: simplicity, transparency (show the agent's planning steps), and the agent-computer interface (ACI) | not framed as three principles, but its tool advice is the same | agree, with one correction: the third is **tool** documentation and testing, not my own thoughts |
| Guardrails are layered: classifier, regex and rules, and an LLM check, plus output checks for the brand | parallel guardrail passes are an example of parallelisation | no single guardrail is enough, so layer them: relevance and safety classifiers, a PII filter, moderation, rules such as regex and blocklists, tool safeguards, output validation | agree; the guide also adds tool risk ratings and human escalation |
| Build guardrails for the vulnerabilities I have found, and add more as I go | agents need extensive sandbox testing and guardrails because errors compound | start from the risks already identified, data privacy and content safety first, and add as real failures appear | agree |
| A workflow follows a predefined path; an agent directs its own process | this is its definition of the two | an agent runs a workflow on a user's behalf with a high degree of independence and decides what happens next | agree |
| If the problem cannot be predefined, use an agent | agents suit open-ended problems where the number of steps cannot be predicted or hardcoded | three signals: complex decisions, rules too hard to maintain, and heavy use of unstructured data | agree |

---

## Workflows against agents

| | Workflow | Agent |
| --- | --- | --- |
| Who decides the next step | my code, on a path I wrote | the model, at run time |
| Predictability | high: the same path every run | lower: the number of steps and the route vary |
| Cost and latency | low and bounded | higher, and harder to bound |
| Failure | a known step fails, so I know where to look | errors compound across steps (at 95% per step, 10 steps succeed 60% of the time) |
| Best for | well-defined tasks where predictability matters | open-ended problems where the steps cannot be hardcoded |
| What I must add | tests per step | step limits, budgets, tracing and approvals (the 15 controls) |

**My own projects, sorted:** the health RAG is a **workflow**: retrieve, answer with citations, abstain
if the evidence is weak. The task API worker is a workflow. The Phase 2 operations agent is the first
real **agent**, because the route to a root cause depends on what the logs show.

---

## The five workflow patterns (Anthropic)

| Pattern | What it does | Fits when | Where I could use it |
| --- | --- | --- | --- |
| **Prompt chaining** | fixed sequential steps, each using the previous output, with optional checks between steps | the task splits cleanly into subtasks, and I will pay latency for accuracy | health RAG: retrieve, draft, check each claim against its source, then answer |
| **Routing** | classify the input, then send it to a specialised path or model | distinct categories are handled better apart, or easy questions can go to a cheaper model | triage: in scope, out of scope or urgent; a small model for easy questions |
| **Parallelisation** | run subtasks at the same time (sectioning), or run one task several times and compare (voting) | speed matters, or several views raise confidence | guardrail checks beside the main answer; three judge runs, then a majority vote |
| **Orchestrator-workers** | a central model splits the task, hands pieces to worker models and combines the results | the subtasks cannot be predicted in advance | Capstone 3B: a supervisor with specialists for tickets, runbooks and approvals |
| **Evaluator-optimiser** | one model produces, another critiques, and they loop | there are clear criteria and refinement measurably helps | generate an answer, judge it, revise (the week 21 judge) |

**Reading the list as a ladder:** chaining and routing are the simplest, so I reach for them first.
Orchestrator-workers is already close to an agent, because the model decides the subtasks. That is why
Capstone 3B comes after the single-agent capstones.

---

## When to build an agent, and when not to

**Anthropic:** use workflows for well-defined tasks; use agents when flexibility and model-driven decisions
are needed. Agents suit open-ended problems where the steps cannot be predicted or hardcoded. They cost
more and errors can compound, so they need extensive sandbox testing and guardrails.

**OpenAI's three signals** that a workflow suits an agent, where deterministic automation struggles:

1. **Complex decisions:** nuanced judgement, exceptions, context-sensitive choices (a refund approval).
2. **Rules too hard to maintain:** large rulesets that are costly or error-prone to update (a vendor
   security review).
3. **Unstructured data:** natural language, documents and conversation (an insurance claim).

If a use case meets none of these, a deterministic solution may be enough.

**My rule, in order:**

1. Can I write the steps down? Build a **workflow**.
2. Does one prompt with retrieval and examples reach my target on my evaluation set? **Stop there.**
3. Does the route depend on what the system finds, and can I check the outcome? Build a **single agent**.
4. Is one agent failing because its tools overlap, or its prompt has too many branches? Only then
   consider **several agents**.

---

## Three principles for an agent (Anthropic)

| Principle | What it means | How I will apply it |
| --- | --- | --- |
| **Simplicity** | keep the design as small as the task allows | a plain loop and the raw model API first; a framework only when I understand what it hides |
| **Transparency** | show the agent's planning steps | log every step, tool call and result in `tool_calls`; show a person the evidence behind a conclusion |
| **ACI: the agent-computer interface** | design the tools with "thorough tool documentation and testing" | write each tool description for a new colleague; test with many example calls; make arguments hard to misuse |

**On frameworks:** Anthropic suggests starting with the model API directly, since many patterns take only
a few lines of code. A framework helps with the low-level work but adds layers that hide prompts and
responses, which makes debugging harder. That is the reason weeks 15 and 16 compare four SDKs.

**On tools:** Anthropic gives tool definitions as much prompt-engineering effort as the main prompt. One
example: making a tool require absolute file paths removed the errors that relative paths caused.

---

## OpenAI's building blocks

| Block | What it is | Notes for my loop |
| --- | --- | --- |
| **Model** | the LLM that reasons and decides | set up evaluations for a baseline, reach the accuracy target with the strongest model, then try smaller models for cost and speed |
| **Tools** | functions and APIs the agent uses to act | data tools read (databases, search), action tools change state (send, update, escalate), orchestration tools let one agent call another |
| **Instructions** | explicit rules for behaviour | turn existing procedures into steps, tie each step to an action, cover edge cases with branches |

**Single agent or several:**

- A single agent runs in a loop until an exit condition: a final answer, a reply with no tool call, an
  error, or a turn limit. That last exit is my step limit.
- Several agents come in two shapes: a **manager** that calls specialist agents as tools and keeps
  control, or **decentralised** peers that hand control to one another.
- OpenAI's advice is to get the most out of a single agent first. Split when the prompt has many nested
  conditions, or when tools overlap so much that clearer names and descriptions do not fix the choices.

---

## Guardrails: layers

No single guardrail is enough, so I stack cheap ones with stronger ones. My reading of the OpenAI list,
ordered by cost:

| Layer | What it catches | Cost | In my projects |
| --- | --- | --- | --- |
| **Rules:** regex, blocklists, input length limits | known bad patterns and oversize inputs | almost free, deterministic | cap input length; strip secrets and card-like numbers; refuse known injection strings |
| **Classifiers:** relevance, and safety (jailbreaks, prompt injection) | off-topic input; attempts to take over the agent | a small model call | health RAG: refuse questions outside the six booklets |
| **LLM-based check** (my reading: a model judges an input or output) | what rules cannot express, such as "is this answer supported by the sources?" | an extra model call per check | the groundedness judge from week 21 |
| **PII filter and moderation** | personal data and harmful content in outputs | cheap to moderate | redact before logging; moderate before display |
| **Tool safeguards** | risky actions: rate each tool low, medium or high by write access, reversibility, permissions and financial impact | design time, then free | `read_logs` low; `scale_deployment` medium; `restart_pod` high, so it needs approval |
| **Output validation** | replies that break the brand or policy | a rule or a model call | tone, no diagnosis or dosing beyond the cited source, always cite |

**How to build them:**

- Start from the **vulnerabilities I have already found**, data privacy and content safety first.
- **Add a guardrail each time a real failure appears**, so the set grows from evidence.
- Balance security against user experience: a guardrail that blocks good requests costs trust.
- Keep one line per guardrail in `DECISIONS.md`: the vulnerability, the layer, and the test that proves it.

**Human intervention:** OpenAI names two triggers for handing over to a person.

1. A **failure threshold** is passed, such as repeated failures to understand the request. For my loop
   this is the step limit and the loop detector.
2. A **high-risk action** is attempted, such as cancelling an order, a large refund or a payment. Keep a
   person in the loop until the agent has earned trust.

---

## How this changes my plan

- **Wed 25 Nov, the agent loop:** write the plain loop first with a turn limit as its exit. Log every
  step. Start with read-only tools.
- **Wed 2 Dec, the controls:** add the tool risk ratings, the approval gate for high-risk tools, and the
  step and tool-call limits. These are controls 1, 2, 8 and 9 on the 15-control checklist.
- **Before each new layer:** run the evaluation first, and add the layer only if it improves the result.
- **Capstone 3B:** use orchestrator-workers only after the single-agent version is measured and
  its tools are clear.

## Questions I still have

1. How do I measure that two tools overlap enough to justify splitting into separate agents?
2. At what failure rate should an agent escalate to a person: a fixed number of attempts, or a rate over
   many tasks?

## In an interview, in one sentence each

- **Workflow or agent?** A workflow follows a path I wrote; an agent chooses its own. I use a workflow
  when I can write the steps down, and an agent only when the route depends on what the system finds.
- **How do you build guardrails?** In layers: cheap rules first, then classifiers, then a model check,
  with tool risk ratings and human approval for high-risk actions. I start from the vulnerabilities I
  have found and add one for each real failure.