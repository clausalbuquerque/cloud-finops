#!/usr/bin/env python3
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import sys
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

# Setup
from finops_ai.orchestration import FinOpsFlow
from finops_ai.agents.finops_agent import create_finops_agent
from finops_ai.agents.sre_agent import create_sre_agent
from finops_ai.memory import AgentMemoryRepository
from finops_ai.llm import _load_env

_load_env()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("finops-agent-api")

app = FastAPI(title="FinOps Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_url = os.getenv("DATABASE_URL") or "postgresql+psycopg://postgres:postgres123@localhost:5433/cloud_finops"
memory_repo = None
if db_url:
    try:
        repo = AgentMemoryRepository.from_url(db_url)
        repo.get_interaction_memory(limit=1)
        memory_repo = repo
        logger.info("Connected to AgentMemoryRepository.")
    except Exception as exc:
        logger.warning(f"AgentMemoryRepository unavailable ({exc}), running in-memory fallback.")

executor = ThreadPoolExecutor(max_workers=4)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "finops-agent-api"}


@app.get("/")
async def root():
    return {"status": "ok", "message": "Cloud FinOps AI Agent API is running"}


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    body = await request.json()
    query = body.get("query")
    team = body.get("team")

    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def step_callback(step):
        try:
            def emit_thought(content):
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    "data: " + json.dumps({"type": "THOUGHT", "content": content}) + "\n\n",
                )

            if hasattr(step, "thought") and step.thought:
                emit_thought(step.thought)
            elif hasattr(step, "text") and step.text:
                emit_thought(step.text)
            elif isinstance(step, str):
                emit_thought(step)
            elif isinstance(step, tuple) and len(step) > 0:
                if hasattr(step[0][0], "thought"):
                    emit_thought(step[0][0].thought)
                elif isinstance(step[0][0], str):
                    emit_thought(step[0][0])
                else:
                    emit_thought(str(step))
            else:
                emit_thought(str(step))
        except Exception:
            pass

    finops = create_finops_agent(step_callback=step_callback, verbose=False)
    sre = create_sre_agent(step_callback=step_callback, verbose=False)

    flow = FinOpsFlow(
        memory_repo=memory_repo,
        finops_agent=finops,
        sre_agent=sre,
    )

    async def event_generator():
        yield "data: " + json.dumps({"type": "THOUGHT", "content": "Analyzing your query and context..."}) + "\n\n"

        def run_flow():
            try:
                res = flow.execute_flow(
                    query=query,
                    session_id=str(uuid4()),
                    team_scope=team,
                    status_callback=step_callback,
                )
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    "data: " + json.dumps({"type": "FINAL_RESPONSE", "content": res.final_response}) + "\n\n",
                )
            except Exception as e:
                logger.exception("Error executing flow")
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    "data: " + json.dumps({"type": "FINAL_RESPONSE", "content": f"Error: {str(e)}"}) + "\n\n",
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, "data: [DONE]\n\n")

        executor.submit(run_flow)

        while True:
            chunk = await queue.get()
            yield chunk
            if chunk == "data: [DONE]\n\n":
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Starting FinOps Agent FastAPI on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

