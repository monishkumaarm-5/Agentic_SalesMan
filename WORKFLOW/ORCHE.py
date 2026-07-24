import os
from typing import TypedDict
from AGENTS.MOBILE_SALES_AGENT import MOBILE_SALES_AGENT
from AGENTS.LAPTOP_SALES_AGENT import LAPTOP_SALES_AGENT
from AGENTS.HEADPHONE_SALES_AGENT import HEADPHONE_SALES_AGENT
from AGENTS.ENTRYSAFEGAURD_AGENT import isvalidquery
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from  DATABASE import SQL_CONNECTOR
from DATABASE.SQL_CONNECTOR import DB_CONNECTOR
import config

os.environ["GOOGLE_API_KEY"] = config.GOOGLE_API_KEY

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0
)

class Graph_State(TypedDict):
    question: str
    answer: str
    context: str

def entry_gaurd_agent(state:Graph_State):
    question=state["question"]
    valid=isvalidquery(question)
    if valid["query"]:
        print("Entry Guard : Query Accepted")
        if(valid["mobile"]):
            state["context"]="MOBILE"
        elif (valid["laptop"]):
            state["context"] = "LAPTOP"
        elif (valid["headphone"]):
            state["context"] = "HEADPHONE"
        return state
    else:
        print("Entry Guard : Query Rejected")
        return {
            "context": "DENY",
            "answer": (
                "Sorry, I can only answer questions related to "
                "phones, laptops and headphones."
            )
        }

def router(state:Graph_State):
    if state["context"]=="DENY":
        return "chatbot"
    elif state["context"]=="HEADPHONE":
        return "headphone_sales_Agents"
    elif state["context"] == "MOBILE":
        return "mobile_sales_Agents"
    elif state["context"] == "LAPTOP":
        return "laptop_sales_Agents"
    elif state["context"]=="END":
        return END
    else:
        return "chatbot"

vector=DB_CONNECTOR()

def headphone_sales_Agents(state:Graph_State):
    query=state["question"]
    db=vector.headphone_vector_database()
    docs = db.similarity_search(query, k=3)
    rag_data = "\n\n".join(doc.page_content for doc in docs)
    state["answer"] = HEADPHONE_SALES_AGENT(query,rag_data)
    return state
def laptop_sales_Agents(state: Graph_State):
    query=state["question"]
    db = vector.laptop_vector_database()
    docs = db.similarity_search(query, k=3)
    rag_data = "\n\n".join(doc.page_content for doc in docs)
    state["answer"] =LAPTOP_SALES_AGENT(query,rag_data)
    return state

def mobile_sales_Agents(state:Graph_State):
    query=state["question"]
    db = vector.phone_vector_database()
    docs = db.similarity_search(query, k=3)
    rag_data = "\n\n".join(doc.page_content for doc in docs)
    state["answer"] =MOBILE_SALES_AGENT(query,rag_data).raw
    return state

def exit_gaurd_agent (state:Graph_State):
    "yet to implement"
    pass


builder = StateGraph(Graph_State)

builder.add_node("entry_guard_agent", entry_gaurd_agent)
builder.add_node("headphone_sales_Agents", headphone_sales_Agents)
builder.add_node("laptop_sales_Agents", laptop_sales_Agents)
builder.add_node("mobile_sales_Agents", mobile_sales_Agents)



builder.add_edge(START, "entry_guard_agent")
builder.add_conditional_edges("entry_guard_agent",router)
builder.add_edge("headphone_sales_Agents", END)
builder.add_edge("laptop_sales_Agents", END)
builder.add_edge("mobile_sales_Agents", END)

graph = builder.compile(
    checkpointer=MemorySaver()
)


# -------------------------
# Config
# -------------------------
config = {
    "configurable": {
        "thread_id": "demo"
    }
}


# -------------------------
# First Run
# -------------------------
result = graph.invoke(
    {
        "question": "I want high qualtiy headphone please give me "
    },
    config=config
)

print(result["answer"])