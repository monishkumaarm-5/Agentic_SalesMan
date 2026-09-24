"""The real prompt templates must render with exactly the variables the
workflow passes -- a stray {brace} would otherwise only fail against the
live LLM."""
from langchain_core.prompts import ChatPromptTemplate

from app.agents import advisor, recommender, understanding
from app.agents.advisor import AdvisorOutput
from tests.conftest import understanding as make_understanding


def render(module, variables):
    prompt = ChatPromptTemplate.from_messages([("system", module.SYSTEM), ("human", module.USER)])
    assert set(prompt.input_variables) == set(variables), set(prompt.input_variables) ^ set(variables)
    return "\n".join(m.content for m in prompt.format_messages(**variables))


def test_all_prompts_render(run, agents):
    run("phones")
    agents.next_understanding = make_understanding(action="discuss", referenced=["Redmi Note 14"])
    agents.advice = AdvisorOutput(message="ok")
    run("tell me about the redmi")

    text = render(understanding, agents.calls["understand"][-1])
    assert "Redmi Note 14" in text and "Mobile: 3 products" in text
    text = render(recommender, agents.calls["recommend"][0])
    assert "fit score" in text and "₹18,999" in text
    text = render(advisor, agents.calls["advise"][0])
    assert "Redmi Note 14" in text


def test_mcp_server_registers_tools():
    import asyncio

    from app.mcp_server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"list_categories", "search_products", "compare_products", "check_stock"} <= names
