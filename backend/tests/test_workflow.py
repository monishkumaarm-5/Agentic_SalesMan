"""End-to-end workflow behaviour with scripted agents."""
from app.agents.advisor import AdvisorOutput
from tests.conftest import understanding


def test_greeting_is_answered_directly_without_searching(run, agents):
    agents.next_understanding = understanding(action="reply", reply="Hi! What are you shopping for?", categories=[])
    state = run("hello")
    assert state["turn"]["answer"] == "Hi! What are you shopping for?"
    assert state["turn"]["response_type"] == "message"
    assert agents.calls["recommend"] == []
    assert state["messages"][-2:] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hi! What are you shopping for?"},
    ]


def test_a_greeting_with_a_request_is_not_swallowed(run, agents):
    # The model (not a phrase list) decides; a greeting-prefixed request
    # goes straight to recommendations.
    agents.next_understanding = understanding(action="recommend", budget_max=30000)
    state = run("hey, show me phones under 30k")
    assert state["turn"]["response_type"] == "recommendation"


def test_recommendation_builds_grounded_cards_in_the_models_order(run, agents):
    agents.next_understanding = understanding(budget_max=30000, must_haves=["AMOLED"])
    state = run("phone under 30000 with amoled")
    [group] = state["turn"]["recommendations"]
    names = [c["name"] for c in group["picks"]]
    assert names[:2] == ["Redmi Note 14", "Galaxy M35 5G"]
    assert len(names) == 3  # topped up to picks_per_category from the scored list
    top = group["picks"][0]
    assert top["price"] == 18999 and top["headline"] == "Redmi Note 14 headline"
    assert top["match"]["overall"] > 0
    assert any("budget" in r.lower() for r in top["fit_reasons"])
    assert state["shown"]["Mobile"][0]["name"] == "Redmi Note 14"


def test_hallucinated_pick_names_are_ignored(run, agents):
    agents.recommend_picks = ["Nokia 9000 Communicator"]
    state = run("phones please")
    names = [c["name"] for c in state["turn"]["recommendations"][0]["picks"]]
    assert "Nokia 9000 Communicator" not in names and len(names) == 3


def test_recommending_without_a_category_asks_instead(run, agents):
    agents.next_understanding = understanding(action="recommend", categories=[])
    state = run("recommend something")
    assert state["turn"]["response_type"] == "clarification"
    assert "?" in state["turn"]["answer"]
    assert agents.calls["recommend"] == []


def test_unknown_categories_are_dropped(run, agents):
    agents.next_understanding = understanding(action="recommend", categories=["Spaceship", "mobile"])
    state = run("spaceship or phone")
    assert state["profile"]["categories"] == ["Mobile"]


def test_clarifying_questions_are_capped(run, agents):
    agents.next_understanding = understanding(action="clarify", reply="What's your budget?")
    for _ in range(3):
        assert run("a phone")["turn"]["response_type"] == "clarification"
    state = run("a phone")
    assert state["turn"]["response_type"] == "recommendation"
    assert state["turn"]["policy"] == "clarify_limit_reached"


def test_alternatives_exclude_what_was_already_shown(run, agents, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "picks_per_category", 2)
    run("phones")
    agents.next_understanding = understanding(action="alternatives")
    agents.recommend_picks = []
    state = run("show me something else")
    names = [c["name"] for c in state["turn"]["recommendations"][0]["picks"]]
    assert names == ["iPhone 15"]


def test_alternatives_when_everything_was_shown_says_so(run, agents):
    run("phones")  # shows all 3 phones
    agents.next_understanding = understanding(action="alternatives")
    state = run("anything else?")
    assert state["turn"]["response_type"] == "message"
    assert "all the mobile options" in state["turn"]["answer"]


def test_discuss_uses_catalog_data_and_returns_a_comparison(run, agents):
    run("phones")
    agents.next_understanding = understanding(action="discuss", referenced=["Redmi Note 14", "Galaxy M35 5G"])
    agents.advice = AdvisorOutput(message="| | Redmi | Galaxy |", compare_products=["Redmi Note 14", "Galaxy M35 5G"])
    state = run("compare the first two")
    assert state["turn"]["response_type"] == "comparison"
    assert [c["name"] for c in state["turn"]["comparison"]] == ["Redmi Note 14", "Galaxy M35 5G"]
    assert "Redmi Note 14" in agents.calls["advise"][0]["products"]


def test_discuss_with_nothing_to_discuss_recommends(run, agents):
    agents.next_understanding = understanding(action="discuss")
    assert run("is it good?")["turn"]["response_type"] == "recommendation"


def test_understanding_failure_falls_back_gracefully(run, agents):
    agents.fail.add("understand")
    state = run("hi")
    assert state["turn"]["response_type"] == "clarification"
    assert state["turn"]["answer"]
    assert state["turn"]["suggestions"]  # built from the live categories


def test_recommender_failure_still_shows_products(run, agents):
    agents.fail.add("recommend")
    state = run("phones")
    assert state["turn"]["response_type"] == "recommendation"
    assert "Redmi Note 14" in state["turn"]["answer"] or "Galaxy" in state["turn"]["answer"]


def test_empty_and_oversized_messages_skip_the_llm(run, agents):
    assert run("   ")["turn"]["answer"]
    assert run("x" * 5000)["turn"]["answer"]
    assert agents.calls["understand"] == []


def test_profile_persists_and_turn_data_resets(run, agents):
    run("phones")
    agents.next_understanding = understanding(action="reply", reply="We're open 10 to 9.", budget_max=30000)
    state = run("when are you open?")
    assert state["profile"]["budget_max"] == 30000
    assert "recommendations" not in state["turn"]
    assert len(state["messages"]) == 4


def test_context_passed_to_the_model(run, agents):
    run("phones")
    run("more")
    variables = agents.calls["understand"][-1]
    assert "Mobile: 3 products" in variables["catalog"]
    assert "Redmi Note 14" in variables["shown"]
    assert "USER: phones" in variables["history"]
    assert "Trein T Nagar" in variables["store"]
