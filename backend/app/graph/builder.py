import logging
import sqlite3
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.core.config import Settings
from app.graph.nodes import Nodes
from app.graph.state import ChatState
from app.graph.toolkit import Toolkit
from app.graph.tracing import NODE_AGENTS, traced_node, traced_router

logger = logging.getLogger("salesman.graph")


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
    log = settings.log_graph_state
    g = StateGraph(ChatState)
    for name in ("guard", "understand", "retrieve", "recommend", "advise", "finalize"):
        g.add_node(name, traced_node(name, getattr(nodes, name), log))

    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", traced_router("guard", nodes.route_after_guard, log),
                            ["understand", "finalize"])
    g.add_conditional_edges("understand", traced_router("understand", nodes.route_after_understand, log),
                            ["retrieve", "advise", "finalize"])
    g.add_conditional_edges("retrieve", traced_router("retrieve", nodes.route_after_retrieve, log),
                            ["recommend", "finalize"])
    g.add_edge("recommend", "finalize")
    g.add_edge("advise", "finalize")
    g.add_edge("finalize", END)

    if checkpointer is None:
        checkpointer = sqlite_checkpointer(settings.checkpoint_db_path)
    graph = g.compile(checkpointer=checkpointer)
    if log:
        log_graph_structure(graph)
    return graph


def log_graph_structure(graph) -> None:
    """Logs the compiled workflow (nodes, agents, edges) once at startup."""
    drawn = graph.get_graph()
    lines = ["Workflow graph:"]
    for node_id in drawn.nodes:
        if node_id.startswith("__"):
            continue
        lines.append(f"  [{node_id}] {NODE_AGENTS.get(node_id, '')}")
    for edge in drawn.edges:
        style = "-->" if not edge.conditional else "-?->"
        lines.append(f"  {edge.source} {style} {edge.target}")
    logger.info("\n".join(lines))
