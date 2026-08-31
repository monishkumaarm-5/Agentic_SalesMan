from AGENTS.SALES_CREW_FACTORY import build_sales_crew

crew = build_sales_crew(category="Mobile", product_noun="phone")


def MOBILE_SALES_AGENT(user_request, rag_data):
    result = crew.kickoff(
        inputs={
            "user_request": user_request,
            "rag_data": rag_data,
        }
    )
    return result
