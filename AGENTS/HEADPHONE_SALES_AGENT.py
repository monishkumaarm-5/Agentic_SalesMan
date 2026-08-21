from langchain_core.prompts import PromptTemplate
from crewai import Agent, Task, Crew, LLM

import config

# CrewAI agents talk to Gemini through litellm, which -- for the "gemini/..."
# model prefix -- reads GEMINI_API_KEY, not GOOGLE_API_KEY. Building the LLM
# explicitly with api_key= sidesteps that env-var mismatch entirely instead
# of relying on litellm picking the right variable up from the environment.
llm = LLM(
    model="gemini/gemini-3.5-flash-lite",
    api_key=config.GOOGLE_API_KEY,
)
product_prompt = PromptTemplate.from_template("""
You are a Senior Headphone Product Expert.

Goal:
Analyze the customer's request and the retrieved RAG data.

Responsibilities:
- Understand customer requirements.
- Compare available headphones.
- Recommend ONLY products present in the RAG data.
- Never invent specifications.
- Explain why the recommended headphone best matches the customer's needs.

Return JSON:

{{
    "recommended_product":"",
    "reason":"",
    "key_features":[],
    "buy_link":""
}}

User Request:
{user_request}

RAG Data:
{rag_data}
""")

psychology_prompt = PromptTemplate.from_template("""
You are an Expert Consumer Psychologist.

Your job is to understand WHY the customer wants headphones.

Identify

- Buying intent
- Pain points
- Emotional motivation
- Budget sensitivity
- Urgency
- Purchase confidence

Suggest the best persuasion strategy.

Return JSON:

{{
    "customer_type":"",
    "pain_points":[],
    "motivation":"",
    "selling_strategy":"",
    "urgency_level":"Low/Medium/High"
}}

User Request:
{user_request}
""")

story_prompt = PromptTemplate.from_template("""
You are a Professional Sales Storytelling Expert.

Using the recommended headphone and customer psychology,

Generate a short story that emotionally connects the customer with the product.

Rules

- Keep under 120 words.
- Be natural.
- Do NOT exaggerate.
- Focus on solving the customer's problem.
- End with a gentle call to action.
""")

sales_prompt = PromptTemplate.from_template("""
Role:
Senior Headphone Sales Consultant.

Instructions

1. Introduce the recommended headphone.
2. Explain why it matches the customer's needs.
3. Highlight only verified features.
4. Include the storytelling paragraph naturally.
5. Mention any available offers only if present in the RAG data.
6. Encourage the customer to purchase without using manipulative or false scarcity.
7. Include the official purchase link from the RAG data.
8. Never invent links or specifications.

Return Markdown.

Format

# Recommended Headphone

Product Name

explain Why this Headphone?

explain Key Features

explain Story

Buy Now

Official Purchase Link
""")

product_agent = Agent(
    role="Senior Headphone Product Expert",
    goal="Recommend the best headphone from RAG data",
    backstory="Expert in comparing headphones using only verified product information.",
    llm=llm,
    verbose=True
)

psychology_agent = Agent(
    role="Consumer Psychologist",
    goal="Understand customer buying intent",
    backstory="Specialist in consumer psychology and purchasing behavior.",
    llm=llm,
    verbose=True
)

story_agent = Agent(
    role="Storytelling Expert",
    goal="Create emotional product stories",
    backstory="Creates engaging but truthful stories for customers.",
    llm=llm,
    verbose=True
)

sales_agent = Agent(
    role="Headphone Sales Consultant",
    goal="Generate the final sales response",
    backstory="Combines technical knowledge with customer psychology.",
    llm=llm,
    verbose=True
)

product_task = Task(
    description=product_prompt.format(
        user_request="{user_request}",
        rag_data="{rag_data}"
    ),
    expected_output="Short Crispy and punchy",
    agent=product_agent
)

psychology_task = Task(
    description=psychology_prompt.format(
        user_request="{user_request}"
    ),
    expected_output="Short Crispy and punchy",
    agent=psychology_agent,
    context=[product_task]
)

story_task = Task(
    description=story_prompt.format(),
    expected_output="Short Crispy and punchy",
    agent=story_agent,
    context=[
        product_task,
        psychology_task
    ]
)

sales_task = Task(
    description=sales_prompt.format(),
    expected_output="Short Crispy and punchy for chatting user",
    agent=sales_agent,
    context=[
        product_task,
        psychology_task,
        story_task
    ]
)

crew = Crew(
    agents=[
        product_agent,
        psychology_agent,
        story_agent,
        sales_agent
    ],
    tasks=[
        product_task,
        psychology_task,
        story_task,
        sales_task
    ],
    verbose=True
)

def HEADPHONE_SALES_AGENT(user_request, rag_data):
    result = crew.kickoff(
        inputs={
            "user_request": user_request,
            "rag_data": rag_data
        }
    )
    return result


"""
result = crew.kickoff(
    inputs={
        "user_request": user_query,
        "rag_data": retrieved_documents
    }
)

print(result)
"""