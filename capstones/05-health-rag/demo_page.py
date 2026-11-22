import json
import logging
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import streamlit as st

TIMEOUT = httpx.Timeout(
    5.0, read=120.0
)  # fail fast if the API is down; wait for the answer
API = os.environ.get("HEALTH_RAG_API_URL", "http://localhost:8000")
logger = logging.getLogger(__name__)


def ask(question: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (event, data) pairs from POST /v1/ask."""
    with httpx.stream(
        "POST",
        f"{API}/v1/ask",
        json={"question": question},
        headers={"X-API-Key": os.environ["HEALTH_RAG_API_KEY"]},
        timeout=TIMEOUT,
    ) as r:
        r.raise_for_status()
        event = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: ") and event:
                yield event, json.loads(line.removeprefix("data: "))


@dataclass
class Reply:
    kind: str = "error"  # "answer", "abstain" or "error"
    text: str = ""
    reason: str | None = None
    cited: list[str] = field(default_factory=list[str])
    sources: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    seconds: float = 0.0


def get_reply(question: str) -> Reply:
    reply = Reply()
    start = time.perf_counter()
    for event, data in ask(question):
        if event == "answer":
            reply.kind, reply.text = "answer", data["text"]
        elif event == "citations":
            reply.cited = [c["id"] for c in data["citations"]]
        elif event == "abstain":
            reply.kind, reply.text, reply.reason = (
                "abstain",
                data["text"],
                data["reason"],
            )
        elif event == "sources":
            reply.sources = data["sources"]
        elif event == "error":
            reply.kind, reply.text = "error", data["message"]
    reply.seconds = time.perf_counter() - start
    return reply


def error_message(exc: httpx.HTTPError) -> str:
    """One plain sentence for the user, with a next step. Never the raw exception."""
    if isinstance(exc, httpx.ConnectError):
        return "The answer service isn't running. Start it and try again."
    if isinstance(exc, httpx.TimeoutException):
        return "This is taking too long. Please try again in a moment."
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return "This page isn't set up with a valid key. Check HEALTH_RAG_API_KEY."
        if status == 422:
            return "Questions must be 1 to 2,000 characters."
        if status == 429:
            wait = exc.response.headers.get("Retry-After")
            when = f"{wait} seconds" if wait else "a few seconds"
            return f"Too many questions at once. Wait {when} and try again."
        if status == 501:
            return "Question answering isn't switched on in the API (HEALTH_RAG_DATABASE_URL isn't set)."
        if status >= 500:
            return "The answer service had a problem. Please try again in a moment."
    return "Something went wrong while asking. Please try again."


def is_retryable(exc: httpx.HTTPError) -> bool:
    """Worth pressing Retry: the problem may go away on its own."""
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and (
        exc.response.status_code == 429 or exc.response.status_code >= 500
    )


def run_question(question: str) -> None:
    st.session_state["last_question"] = question
    with st.status("Searching the booklets and checking the answer…") as box:
        try:
            reply = get_reply(question)
        except httpx.HTTPError as exc:
            logger.exception("ask failed")  # the full detail, for you, in the terminal
            box.update(label="Couldn't answer", state="error")
            st.session_state["reply"] = Reply(kind="error", text=error_message(exc))
            st.session_state["retryable"] = is_retryable(exc)
        else:
            box.update(label=f"Done in {reply.seconds:.0f} s", state="complete")
            st.session_state["reply"] = reply
            st.session_state["retryable"] = False


def request_retry() -> None:
    st.session_state["retry"] = True


def main() -> None:
    st.set_page_config(page_title="Health booklet assistant")
    st.title("Health booklet assistant")
    st.caption(
        "Answers only from the six health booklets, with sources. "
        "If the booklets don't cover it, it says so."
    )

    with st.form("ask"):
        question = st.text_area("Your question", max_chars=2000)
        submitted = st.form_submit_button("Ask")
    if st.session_state.pop("retry", False):
        run_question(st.session_state["last_question"])
    elif submitted:
        if not question.strip():
            st.warning("Type a question first.")
        else:
            run_question(question.strip())

    reply = st.session_state.get("reply")
    if reply is None:
        return

    REASONS = {
        "low_retrieval_score": "nothing in the booklets matched the question closely enough"
    }

    if reply.kind == "answer":
        st.markdown(reply.text)
        st.caption("Sources cited: " + ", ".join(reply.cited))
        st.caption("Generated from the booklets. Check the source before acting on it.")
    elif reply.kind == "abstain":
        st.info("I can't find this in the booklets.")
        st.caption("Why: " + REASONS.get(reply.reason or "", reply.reason or "unknown"))
        st.caption("Try rephrasing, or the question may be outside the six booklets.")
    else:
        st.error(reply.text)
        if st.session_state.get("retryable"):
            st.button("Retry", on_click=request_retry)

    if reply.sources:
        heading = (
            "What it searched"
            if reply.kind == "answer"
            else "What it searched (none was close enough)"
        )
        st.subheader(heading)
        ordered = sorted(
            reply.sources, key=lambda s: (s["id"] not in reply.cited, -s["score"])
        )
        for s in ordered:
            mark = " · ✓ cited" if s["id"] in reply.cited else ""
            with st.expander(f"{s['id']} · score {s['score']:.2f}{mark}"):
                st.write(s["text"])
    elif reply.kind != "error":
        st.caption("Nothing was retrieved.")


if __name__ == "__main__":
    main()
