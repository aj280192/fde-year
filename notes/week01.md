# Week 1 notes

## Mon 5 Oct: AI Engineering ch. 1

### The AI engineering stack, and where I stand

| Layer | Built myself | Only used | Never touched |
| --- | --- | --- | --- |
| Application development (prompts, context, evaluation, interface) | Prompt -> Natural-language-to-Splunk query assistant. <br> Evaluation -> 100-query ground-truth benchmark on accuracy, latency and failure rate. | | Context -> RAG, through libraries. Prompt templates others wrote. Guardrails. <br> Evaluation -> An LLM judge validated against my own labels. <br> Interface -> A chat interface in TypeScript. <br> Agents -> Any agent SDK (Claude Agent SDK, LangGraph, ADK). <br> Observability -> Tracing across an agent and its tools. | 
| Model development (training, fine-tuning, datasets, inference optimisation) | Training -> LoRA and QLoRA fine-tuning of LLMs with distributed training. | Inference optimisation -> Quantised model weights published by others. vLLM's batching and caching as defaults. | Inference optimisation -> Measuring a throughput-against-latency curve. Distillation. <br> Model routing -> A model cascade that routes easy requests to a small model. |
| Infrastructure (serving, compute, data, monitoring) | Serving -> vLLM on a Run:ai Kubernetes cluster with H100s. | Compute -> The Kubernetes cluster. | Compute -> Public cloud. <br> Infrastructure as code -> Terraform. <br> Serving -> Autoscaling on queue depth. An inference gateway with fallback. Multi-tenant isolation and quotas. <br> Performance -> Load testing. <br> Monitoring -> OpenTelemetry. <br> Cost -> A cost-per-task model.|

### Few lines
- The concept of compute management is new and I have never given it a thought before.
- Before I would have invested more on model, prompt, context, etc. But the chapter puts more importance on deciding what the success metrics are, and the accuracy the application needs to deliver before it is considered as successful. Expectation and Evaluation before model, prompt, context, etc.
- Before I would concentrate on whether it works, but I would rather focus on is it reliable enough under different scenarios as primary.
- One question I still have: How would you choose the evaluation for an application? 

### Where this applies
Success metrics and accuracy the application needs applies directly to the improvement of the NLP-to-SPL application.

## Tue 6 Oct: Cheet Sheet

### Project Setup Commands
```
uv init # creates a new Python project by generating a standard configuration file and folder structure uv.lock .venv (lazyly created)
uv add --dev ruff pyright pytest # ruff -> linter and code formatter, pyright -> static type checker, pre-commit -> git precommit hooks and pytest -> testing framework [All added as dev packages]
uv run pre-commit install # installs the pre-commit hooks based on the .pre-commit-config.yaml definition
```