# Designing AI Interfaces · ch. 5 · Output

Louise Macfadyen, *Designing AI Interfaces* (O'Reilly). Read Sat 21 Nov 2026, week 7, 30 minutes.
**Why now:** I built the health RAG demo page today. This chapter is about the last step of the
pipeline: how the answer reaches the person and what they can do with it.

**How to read this note:** the section headings follow the chapter. *What I took from it* is my own
understanding. *What it means for my page* turns each idea into a rule I can check. The rules at the
end are the ones the demo page has to pass.

---

## The one idea

**The output is not the answer.** The model's text is raw material. What the user receives is a
designed thing: the text, plus where it came from, plus what to do next, plus what to do when the
system can't help. A correct answer that the user can't check, read or act on has failed.

---

## Design principles of outputs

| Principle | What I took from it | What it means for my page |
| --- | --- | --- |
| **Clarity** | present the content so it is readable and easy to scan: short, structured, plain words | the answer first, in short paragraphs; no internal codes such as `low_retrieval_score` on screen |
| **Verifiability** | the user must be able to check the answer for themselves | every claim carries a citation id, and each id opens the paragraph it came from |
| **Grounding** | the answer comes from the sources, and the system says so; when the sources don't support an answer, it abstains | the answer is built only from retrieved paragraphs, checked in code before it is shown; "not in the booklets" is a normal outcome |
| **Actionability** | if the user is expected to do something, the output tells them what, clearly | for a "how do I…" question, steps in order; after an abstain, a next step ("rephrase it, or check the booklet index") |
| **Adjustability** | the user can change the output without starting again: ask again, narrow it, shorten it | a "Ask again" path and an editable question; not built yet |
| **Multiturn outputs** | later answers build on earlier ones in a conversation | out of scope: my page answers one question at a time |

**Grounding against verifiability, the difference I nearly missed:**
- *Grounding* is a property of the **system**: the answer is based on the sources.
- *Verifiability* is a property of the **interface**: the user can see that it is.

A grounded answer with no visible sources asks the user to trust me. A verifiable one lets them check.
My page needs both.

---

## Abstaining, and saying why

This is the rule I care most about for a health assistant.

- **Abstain** when the retrieved sources don't support an answer. A confident wrong answer about
  health is worse than no answer.
- **Show why it abstained**, in plain words. "I can't find this in the booklets" alone feels like a
  failure. "Nothing in the booklets matched closely enough" explains it, and the sources it did look
  at, with their low scores, prove it.
- **Make it calm, not alarming:** an information message, not a red error. Declining is the system
  working correctly.
- **Give a next step:** rephrase, or the question may be outside the six booklets.
- **Keep abstain and error apart.** Abstain means "I worked and the answer isn't here". Error means
  "I couldn't work" (service down, timeout). They need different messages and different colours.

---

## Watermarking and detection

Marking generated content so it can be identified as AI-made, for images, video and text, and the
detection systems that look for those marks. The chapter frames this around misuse and the risks of
generated content.

**For my page:** not needed for a private demo. The honest equivalent is a line saying the answer is
generated from the booklets and may be wrong, so the user checks the source before acting.

## Managing problematic outputs

Outputs can be wrong, harmful or off-brand, and the design has to plan for them rather than hope.

**For my page:** two layers already exist. The citation check runs in code and stops unsupported
text before it reaches the user. The abstain rule stops weak retrieval. Missing: an output check for
tone and scope, for example never giving a diagnosis or a dose that the cited paragraph doesn't
state. That is the "output guardrails" layer from Thursday's agents note.

---

## What I would have missed without the chapter

1. **Verifiability is separate from grounding.** I only had grounding.
2. **Adjustability:** letting the user change the output, not just read it.
3. **Watermarking and detection**, as part of output design, not only a policy question.
4. **Problematic outputs need a plan**, not only a check on correct answers.

---

## Rules for the demo page

Each rule is something I can check by looking at the page. Status as of tonight.

| # | Rule | Principle | How I check it | Status |
| --- | --- | --- | --- | --- |
| 1 | The answer comes only from retrieved paragraphs, and unsupported text is never shown | Grounding | the citation check runs before any event is sent | ✅ |
| 2 | Every answer shows its cited ids under it | Verifiability | ask a booklet question; ids appear | ✅ |
| 3 | Every source can be opened to read the paragraph, with cited ones marked and listed first | Verifiability | open an expander; ✓ on cited ones | ✅ |
| 4 | When the sources don't support an answer, it abstains | Grounding | ask "What is the capital of France?" | ✅ |
| 5 | An abstain says why, in plain words, and shows what was searched with the scores | Abstain | the reason is a sentence, not a code; sources listed | ✅ |
| 6 | An abstain is a calm information message, an error is a red message, and they never look the same | Clarity | stop `serve.py` and compare with an abstain | ✅ |
| 7 | While it works, the page says what it is doing | Clarity | the status box shows during the wait | ✅ |
| 8 | The answer is short and scannable; no internal codes or raw exceptions on screen | Clarity | read it as a non-engineer would (Sunday's test) | check Sunday |
| 9 | For a "how do I" question, the answer gives the steps in order | Actionability | ask a procedure question | check Sunday |
| 10 | After an abstain or error, the user is told what to do next | Actionability | each message ends with a next step | to add |
| 11 | The user can ask again or change the question without retyping | Adjustability | the question stays in the box after an answer | to check |
| 12 | A line says the answer is generated and should be checked against the source before acting | Problematic outputs | visible under every answer | to add |

**Out of scope, on purpose:** multiturn conversation, watermarking, and an output check for tone and
scope (rule 12 is the cheap stand-in until then).

## Questions I still have

1. Should the page show the scores at all? They help me explain an abstain, but may confuse a
   non-engineer. Sunday's test will tell.
2. How much of a cited paragraph should be shown before it becomes redistributing the booklets?