import os
from typing import Optional, TypedDict

import config

# The AGENTS modules below instantiate their Gemini clients as soon as they
# are imported, which means GOOGLE_API_KEY has to already be in the
# environment *before* those imports run. `import config` above only reads
# config.py -- it does not touch os.environ -- so the assignment below must
# stay ahead of every `from AGENTS...` import in this file.
if getattr(config, "GOOGLE_API_KEY", None):
    os.environ.setdefault("GOOGLE_API_KEY", config.GOOGLE_API_KEY)

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from AGENTS.ENTRYSAFEGAURD_AGENT import isvalidquery as entry_guard_check
from AGENTS.EXIT_SAFE_GAURD_AGENT import isvalidquery as exit_guard_check
from AGENTS.HEADPHONE_SALES_AGENT import HEADPHONE_SALES_AGENT
from AGENTS.LAPTOP_SALES_AGENT import LAPTOP_SALES_AGENT
from AGENTS.MOBILE_SALES_AGENT import MOBILE_SALES_AGENT
from DATABASE.SQL_CONNECTOR import DB_CONNECTOR

DECLINE_MESSAGE = (
    "Sorry, I can only answer questions related to phones, laptops and headphones."
)


class Graph_State(TypedDict):
    question: str
    answer: str
    context: str


# ---------------------------------------------------------------------------
# Vector store + compiled graph are both expensive to build (they hit MySQL /
# Chroma and construct several CrewAI agents), so they are created lazily on
# first use and cached, rather than at import time. That lets the FastAPI app
# import this module -- and even boot and serve /api/health -- before
# config.py / the database are fully set up.
# ---------------------------------------------------------------------------
_vector_store: Optional[DB_CONNECTOR] = None
_graph = None


def get_vector_store() -> DB_CONNECTOR:
    global _vector_store
    if _vector_store is None:
        _vector_store = DB_CONNECTOR()
    return _vector_store


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------
def entry_gaurd_agent(state: Graph_State):
    question = state["question"]
    valid = entry_guard_check(question)

    if not valid["query"]:
        print("Entry Guard : Query Rejected")
        return {"context": "DENY", "answer": DECLINE_MESSAGE}

    print("Entry Guard : Query Accepted")
    if valid["mobile"]:
        state["context"] = "MOBILE"
    elif valid["laptop"]:
        state["context"] = "LAPTOP"
    elif valid["headphone"]:
        state["context"] = "HEADPHONE"
    else:
        # Query was judged "relevant" but didn't match a product category --
        # fall back to declining instead of crashing the router.
        state["context"] = "DENY"
        state["answer"] = DECLINE_MESSAGE
    return state


def router(state: Graph_State):
    return {
        "DENY": "chatbot",
        "HEADPHONE": "headphone_sales_Agents",
        "MOBILE": "mobile_sales_Agents",
        "LAPTOP": "laptop_sales_Agents",
    }.get(state["context"], "chatbot")


def chatbot(state: Graph_State):
    state.setdefault("answer", DECLINE_MESSAGE)
    return state


def headphone_sales_Agents(state: Graph_State):
    query = state["question"]
    db = get_vector_store().headphone_vector_database()
    docs = db.similarity_search(query, k=3)
    rag_data = "\n\n".join(doc.page_content for doc in docs)
    result = HEADPHONE_SALES_AGENT(query, rag_data)
    state["answer"] = getattr(result, "raw", result)
    return state


def laptop_sales_Agents(state: Graph_State):
    query = state["question"]
    db = get_vector_store().laptop_vector_database()
    docs = db.similarity_search(query, k=3)
    rag_data = "\n\n".join(doc.page_content for doc in docs)
    result = LAPTOP_SALES_AGENT(query, rag_data)
    state["answer"] = getattr(result, "raw", result)
    return state


def mobile_sales_Agents(state: Graph_State):
    query = state["question"]
    db = get_vector_store().phone_vector_database()
    docs = db.similarity_search(query, k=3)
    rag_data = "\n\n".join(doc.page_content for doc in docs)
    result = MOBILE_SALES_AGENT(query, rag_data)
    state["answer"] = getattr(result, "raw", result)
    return state


def exit_gaurd_agent(state: Graph_State):
    """Final safety pass. Confirms the generated answer doesn't leak
    anything beyond product/purchase information before it reaches the
    customer. Runs after every sales agent, right before END."""
    if state.get("context") == "DENY":
        return state

    answer = state.get("answer", "")
    try:
        safe = exit_guard_check(answer)
    except Exception as exc:  # pragma: no cover - defensive, don't block a reply on a guard-model hiccup
        print(f"Exit Guard : check failed ({exc}), passing answer through")
        return state

    if safe:
        print("Exit Guard : Answer Accepted")
    else:
        print("Exit Guard : Answer Rejected")
        state["answer"] = DECLINE_MESSAGE
        state["context"] = "DENY"
    return state


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------
def get_graph():
    global _graph
    if _graph is not None:
        return _graph

    builder = StateGraph(Graph_State)
    builder.add_node("entry_guard_agent", entry_gaurd_agent)
    builder.add_node("chatbot", chatbot)
    builder.add_node("headphone_sales_Agents", headphone_sales_Agents)
    builder.add_node("laptop_sales_Agents", laptop_sales_Agents)
    builder.add_node("mobile_sales_Agents", mobile_sales_Agents)
    builder.add_node("exit_guard_agent", exit_gaurd_agent)

    builder.add_edge(START, "entry_guard_agent")
    builder.add_conditional_edges("entry_guard_agent", router)
    builder.add_edge("chatbot", END)
    builder.add_edge("headphone_sales_Agents", "exit_guard_agent")
    builder.add_edge("laptop_sales_Agents", "exit_guard_agent")
    builder.add_edge("mobile_sales_Agents", "exit_guard_agent")
    builder.add_edge("exit_guard_agent", END)

    _graph = builder.compile(checkpointer=MemorySaver())
    return _graph


def ask(question: str, thread_id: str = "default") -> dict:
    """Single entry point the FastAPI layer (and anything else) calls."""
    graph = get_graph()
    result = graph.invoke(
        {"question": question},
        config={"configurable": {"thread_id": thread_id}},
    )
    return {
        "answer": result.get("answer", DECLINE_MESSAGE),
        "context": result.get("context", "DENY"),
    }


if __name__ == "__main__":
    response = ask("I want high quality headphones please give me")
    print(response["answer"])
