"""Phase 2 + 3 Streamlit assistant (port 8501).

* Manual Q&A (RAG): answers only from the user manual, with sources. No sign-in needed.
* My finances (live data agent): sign in with your own Finance Tracker account; a tool-calling agent reads YOUR data
  through the REST API (read-only) and uses the manual for guidance. The token stays in this browser session only.

Run:  streamlit run ai/rag/chatbot.py --server.port 8501
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from common.api_client import FinanceApiClient  # noqa: E402
from common.llm import MissingApiKeyError  # noqa: E402
from rag.rag_chain import ask_question, build_rag_chain  # noqa: E402

SAMPLE_QUESTIONS = [
    "How do I set a monthly budget?",
    "What account types are supported?",
    "What happens when I exceed my budget?",
    "How is the savings rate calculated?",
    "What transaction categories are available?",
    "How do I pay my credit card bill?",
]
AGENT_QUESTIONS = [
    "Am I over budget on food this month?",
    "What is my total balance across all accounts?",
    "How am I doing on spending and what should I cut?",
    "Show my recent transactions",
]
MODE_FAQ, MODE_AGENT = "Manual Q&A (RAG)", "My finances (live data)"


@st.cache_resource(show_spinner="Loading knowledge base…")
def load_chain():
    return build_rag_chain()


def render_sources(sources):
    if sources:
        with st.expander("📚 Sources from the user manual"):
            for i, s in enumerate(sources, 1):
                st.markdown(f"**{i}. {s['section']}**")
                st.caption(s["snippet"] + ("…" if len(s["snippet"]) >= 200 else ""))


def render_tool_calls(calls):
    if calls:
        with st.expander(f"🔧 {len(calls)} tool call(s)"):
            for c in calls:
                st.markdown(f"**{c['tool']}** `{c['input']}`")
                st.text(c["output"][:600])


def sign_in_form():
    with st.sidebar.form("login"):
        st.caption("Sign in to let the assistant read your finances (read-only).")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            res = FinanceApiClient().login(email.strip(), password)
            if res.ok:
                st.session_state.token = res.data["access_token"]
                st.session_state.agent = None
                st.session_state.agent_messages = []
                st.rerun()
            else:
                st.sidebar.error(res.error)


def get_agent(chain):
    if st.session_state.get("agent") is None:
        from agent.agent import build_agent

        st.session_state.agent = build_agent(token=st.session_state.token, rag_chain=chain)
    return st.session_state.agent


def main():
    st.set_page_config(page_title="Finance Tracker Assistant", page_icon="💰")
    st.title("💰 Finance Tracker Assistant")
    mode = st.sidebar.radio("Mode", [MODE_FAQ, MODE_AGENT])
    key = "messages" if mode == MODE_FAQ else "agent_messages"
    st.session_state.setdefault(key, [])

    try:
        chain = load_chain()
    except MissingApiKeyError as exc:
        st.error(str(exc))
        st.stop()
    except Exception as exc:  # noqa: BLE001
        st.error(f"The assistant could not start: {exc}")
        st.stop()

    with st.sidebar:
        st.header("💡 Try these")
        for q in (SAMPLE_QUESTIONS if mode == MODE_FAQ else AGENT_QUESTIONS):
            if st.button(q, key=f"q_{q}"):
                st.session_state["pending"] = q
        if st.button("Clear conversation"):
            st.session_state[key] = []
            st.rerun()

    if mode == MODE_AGENT:
        st.caption("Answers use your live data (read-only) plus the user manual. Nothing is ever changed.")
        if not st.session_state.get("token"):
            sign_in_form()
            st.info("Sign in from the sidebar to use your live data.")
            st.stop()
        if st.sidebar.button("Sign out"):
            for k in ("token", "agent", "agent_messages"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.caption("Ask how the Personal Finance Tracker works. Answers are grounded in the user manual.")

    for msg in st.session_state[key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            render_sources(msg.get("sources"))
            render_tool_calls(msg.get("tool_calls"))

    question = st.session_state.pop("pending", None) or st.chat_input("Ask a question…")
    if not question:
        return
    history = [HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]) for m in st.session_state[key]]
    st.session_state[key].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        if mode == MODE_FAQ:
            with st.spinner("Searching the manual…"):
                result = ask_question(question, chain)
            st.markdown(result["answer"])
            render_sources(result["source_details"])
            entry = {"role": "assistant", "content": result["answer"], "sources": result["source_details"]}
        else:
            from agent.agent import run_agent

            with st.spinner("Checking your data…"):
                result = run_agent(question, get_agent(chain), chat_history=history)
            calls = [{"tool": a.tool, "input": str(a.tool_input)[:200], "output": str(obs)} for a, obs in result["intermediate_steps"]]
            st.markdown(result["output"])
            render_tool_calls(calls)
            entry = {"role": "assistant", "content": result["output"], "tool_calls": calls}
    st.session_state[key].append(entry)


main()
