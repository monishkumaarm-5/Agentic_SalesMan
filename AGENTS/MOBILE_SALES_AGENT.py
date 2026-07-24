from langchain_core.prompts import PromptTemplate
from crewai import Agent
from crewai import Task
from crewai import Crew
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite"
    )
product_prompt = PromptTemplate.from_template("""
You are a Senior Mobile Product Expert.

Goal:
Analyze the customer's request and the retrieved RAG data.

Responsibilities:
- Understand customer requirements.
- Compare available phones.
- Recommend ONLY products present in the RAG data.
- Never invent specifications.
- Explain why the recommended phone best matches the customer's needs.

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

Your job is to understand WHY the customer wants a phone.

Identify:

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
""")

story_prompt = PromptTemplate.from_template("""
You are a Professional Sales Storytelling Expert.

Using the recommended phone and customer psychology,

Generate a short story that emotionally connects the customer with the product.

Rules:
- Keep under 120 words.
- Be natural.
- Do NOT exaggerate.
- Focus on solving the customer's problem.
- End with a gentle call to action.

""")

sales_prompt = PromptTemplate.from_template("""
Role:
Senior Mobile Sales Consultant.

Instructions

1. Introduce the recommended phone.
2. Explain why it matches the customer's needs.
3. Highlight only verified features.
4. Include the storytelling paragraph naturally.
5. Mention any available offers only if present in the RAG data.
6. Encourage the customer to purchase without using manipulative or false scarcity.
7. Include the official purchase link from the RAG data.
8. Never invent links or specifications.

Return Markdown.

Format

# Recommended Phone

explain Product Name

explain Why this phone?

expalin Key Features

explain Story

Buy Now

Official Purchase Link
""")

product_agent = Agent(
    role="Senior Smartphone Product Expert",
    goal="Recommend the best smartphone from RAG data",
    backstory="Expert in comparing smartphones using only verified product information.",
    llm="gemini/gemini-3.5-flash-lite",
    verbose=True
)

psychology_agent = Agent(
    role="Consumer Psychologist",
    goal="Understand customer buying intent",
    backstory="Specialist in consumer psychology and purchasing behavior.",
    llm="gemini/gemini-3.5-flash-lite",
    verbose=True
)

story_agent = Agent(
    role="Storytelling Expert",
    goal="Create emotional product stories",
    backstory="Creates engaging but truthful stories for customers.",
    llm="gemini/gemini-3.5-flash-lite",
    verbose=True
)

sales_agent = Agent(
    role="Smartphone Sales Consultant",
    goal="Generate the final sales response",
    backstory="Combines technical knowledge with customer psychology.",
    llm="gemini/gemini-3.5-flash-lite",
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
    description=psychology_prompt.format(),
    expected_output="Short Crispy and punchy",
    agent=psychology_agent,
    context=[product_task]
)

story_task = Task(
    description=story_prompt.format(),
    expected_output="Short Crispy and punchy",
    agent=story_agent,
    context=[product_task, psychology_task]
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

def MOBILE_SALES_AGENT(user_request,rag_data):
    result = crew.kickoff(inputs={
        "user_request": user_request,
        "rag_data": rag_data
    })
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
