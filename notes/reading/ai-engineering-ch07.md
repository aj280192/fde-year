# AI Engineering (Huyen) · Chapter 7 · Finetuning

Read: skimmed, 16 Nov 2026. Why I read it: a customer's first question is nearly always "should we fine-tune?", and I need a short, defensible answer.

## The core idea

Fine-tuning is the **last** step, not the first. The order is:

1. **Prompt engineering first.** It is the cheapest change, you see the result in minutes, and it is easy to undo.
2. **Look at *why* the system is bad.**
   - It lacks **knowledge** (your documents, recent facts, private data) → take the **RAG** path.
   - It has the knowledge but the **behaviour** is wrong (format, tone, style, following a procedure) → the **fine-tuning** path.
3. **Before fine-tuning, count the cost against the likely gain.** How much better must it get? What is that worth? What will it cost in data, training, serving and upkeep? Only then decide.

Short version: **information failure → RAG; behaviour failure → fine-tune; and even then, do the arithmetic first.**

## Which problem is it?

| What I see | Likely cause | First move |
| --- | --- | --- |
| Wrong or invented facts about my own documents | the model never saw them | retrieval (RAG) |
| Out-of-date answers | the facts changed after training | retrieval |
| The right facts are in the prompt, yet the model ignores them or formats the answer wrongly | behaviour | a better prompt, then examples in the prompt, then fine-tune |
| Output must follow a strict format or house style, always | behaviour | prompt with examples, then fine-tune |
| It works but a big model is too slow or too expensive | cost and latency | fine-tune a smaller model to do this one task |

My own evidence: in the health assistant, **retrieval fixes moved the number most.** Chunking and a reranker took Recall@5 from 0.531 to 0.691 on held-out questions with no training at all. The abstain rule and the "rules after the sources" prompt fixed behaviour problems that looked like they needed a bigger model.

## Reasons to fine-tune

- **Format and style, consistently, at scale.** A model that must return the same structure every time, or follow a house tone.
- **A smaller, cheaper model for one narrow task.** Train a small model on a big model's good outputs for that task, and serve it for less.
- **Latency.** A small model answers faster, and a short prompt (no long examples) is cheaper per call.
- **A task the base model is bad at, even with good prompts.** The failure has been measured, not guessed.
- **Reducing bias or fixing a repeated bad habit** that prompts do not remove.

## Reasons not to (or not yet)

- **Cost.** Data, training runs, evaluation, serving a custom model, and redoing all of it when the base model changes.
- **It needs data.** Hundreds to thousands of good, consistent examples, and someone has to write or check them.
- **Slow feedback.** A prompt change takes minutes to test; a fine-tune takes days, and might not work.
- **It doesn't reliably add facts.** Facts that change belong in retrieval, where they can be updated and cited.
- **The base model keeps improving.** A new model release can beat a fine-tune of last year's.
- **You own it afterwards:** versions, re-evaluation, drift.
- **Prompts and retrieval are usually enough,** and I have not yet measured them properly.

## The decision, step by step

1. **Write down the failure.** One or two examples, then a test set of at least 50 cases that show it.
2. **Fix the prompt.** Clearer instructions, examples in the prompt, the rules after the sources.
3. **Measure.** If it passes, stop.
4. **Is it knowledge?** Add retrieval. Measure again. Stop if it passes.
5. **Is it behaviour that remains?** Then consider fine-tuning:
   - What gain do I need (e.g. format errors from 8% to under 1%)?
   - What gain is likely? (A small pilot on a few hundred examples gives a hint.)
   - What does it cost in data, training, evaluation, serving, upkeep?
   - Is there a cheaper route, such as a stronger base model, or few-shot examples?
6. **Decide on the numbers,** and write the decision down with them.

## The techniques, in one place

| Term | What it means | Why it matters |
| --- | --- | --- |
| Full fine-tuning | update every weight | needs a lot of GPU memory: weights, gradients and optimizer state all live in memory |
| PEFT (parameter-efficient fine-tuning) | update only a small part | a fraction of the memory and storage |
| LoRA | freeze the model; train small low-rank matrices added to some layers | cheap; the small adapter can be stored and swapped per customer or task |
| QLoRA | LoRA on a base model compressed to 4-bit | fine-tune a large model on one modest GPU |
| Model merging | combine the weights of several models | a way to combine skills without training again |
| Quantization | store numbers with fewer bits | less memory, a little accuracy lost |

Memory is the practical bottleneck: training needs far more memory than just running the model.

## Edge cases and traps

- Fine-tuning on data that looks like the test set makes the score look good and proves nothing. Keep an untouched test set (as with the held-out questions).
- Training on a model's own outputs can copy its mistakes as well as its style.
- A model fine-tuned for one format can get worse at other things. Test on tasks it wasn't trained for.
- If the labels are inconsistent, the model learns the inconsistency. My dataset had one malformed label out of 746, found by checking.
- Check the licence: some providers' terms limit using a model's outputs to train another model.

## "Should we fine-tune?" — the 150-word answer

Usually not first. Fine-tuning means retraining a model on your own examples. It costs money for data, training and upkeep, and it needs hundreds or thousands of good examples, so you wait a long time to learn if it worked. Start cheaper. First, improve the prompt. If the answers are wrong because the model lacks facts, such as your documents or recent data, add retrieval, because fine-tuning does not reliably teach facts. If the facts are there and the behaviour is still wrong, such as the format, tone or steps, fine-tuning is worth considering. Before committing, estimate the cost and the likely gain: how much better must it get, and what is that worth? In my health assistant, chunking and a reranker lifted Recall@5 from 0.531 to 0.691 with no training. Fine-tune when a small model must match a big one, or consistent behaviour at scale pays for the bill.


## What I'd do differently at work

- Before anyone proposes fine-tuning the query assistant, ask for **one example of a bad answer** and decide which kind it is: missing knowledge or wrong behaviour.
- Ask for a **number** to beat, and a small test set, before any training is discussed.