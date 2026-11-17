"""REST API.

Run:   uvicorn app.api:app --reload
Docs:  http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app import __version__
from app.agent import research_company
from app.graph_agent import research_company_loop
from app.llm import OpenAICompatibleLLM
from app.models import ResearchResult
from app.report import to_markdown

app = FastAPI(
    title="Lead Research Agent",
    version=__version__,
    description="Researches a company website and writes a sales brief.",
)

# Swapped out in tests.
get_llm = OpenAICompatibleLLM


class ResearchRequest(BaseModel):
    url: str
    loop: bool = False  # True = LangGraph loop agent


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/research", response_model=ResearchResult)
def research(request: ResearchRequest) -> ResearchResult:
    try:
        if request.loop:
            return research_company_loop(request.url, get_llm())
        return research_company(request.url, get_llm())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Research failed: {exc}")


@app.post("/research/markdown", response_class=PlainTextResponse)
def research_markdown(request: ResearchRequest) -> str:
    return to_markdown(research(request))
