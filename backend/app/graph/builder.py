import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.core.config import Settings
from app.graph.nodes import Nodes
from app.graph.state import ChatState
from app.graph.toolkit import Toolkit


def sqlite_checkpointer(path: Path) -> BaseCheckpointSaver:
    from langgraph.checkpoint.sqlite import SqliteSaver

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def build_graph(toolkit: Toolkit, settings: Settings, checkpointer: BaseCheckpointSaver | None = None):
    nodes = Nodes(toolkit, settings)
    g = StateGraph(ChatState)
    g.add_node("guard", nodes.guard)
    g.add_node("understand", nodes.understand)
    g.add_node("retrieve", nodes.retrieve)
    g.add_node("recommend", nodes.recommend)
    g.add_node("advise", nodes.advise)
    g.add_node("finalize", nodes.finalize)

    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", nodes.route_after_guard, ["understand", "finalize"])
    g.add_conditional_edges("understand", nodes.route_after_understand, ["retrieve", "advise", "finalize"])
    g.add_conditional_edges("retrieve", nodes.route_after_retrieve, ["recommend", "finalize"])
    g.add_edge("recommend", "finalize")
    g.add_edge("advise", "finalize")
    g.add_edge("finalize", END)

    if checkpointer is None:
        checkpointer = sqlite_checkpointer(settings.checkpoint_db_path)
    return g.compile(checkpointer=checkpointer)
