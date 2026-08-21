from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from ENDPOINTS.endpoints import router as api_router

allowed_origins = [
    origin.strip()
    for origin in getattr(config, "ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app = FastAPI(
    title="Agentic SalesMan API",
    description="Multi-agent sales assistant for phones, laptops and headphones.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {"message": "Agentic SalesMan API is running. See /docs for the API reference."}
