#!/usr/bin/env python3
import sys
import json
import os
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="FinOps Agent API")

# Setup
from finops_ai.orchestration import FinOpsFlow
from finops_ai.agents.finops_agent import create_finops_agent
from finops_ai.agents.sre_agent import create_sre_agent
from finops_ai.memory import AgentMemoryRepository
from finops_ai.llm import _load_env

_load_env()

db_url = os.getenv("DATABASE_URL") or "postgresql+psycopg://postgres:postgres123@localhost:5433/cloud_finops"
memory_repo = None
if db_url:
    try:
        repo = AgentMemoryRepository.from_url(db_url)
        repo.get_interaction_memory(limit=1)
        memory_repo = repo
    except Exception:
        pass

executor = ThreadPoolExecutor(max_workers=4)

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    body = await request.json()
    query = body.get("query")
    team = body.get("team", "data-platform")
    
    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def step_callback(step):
        try:
            def emit_thought(content):
                loop.call_soon_threadsafe(queue.put_nowait, "data: " + json.dumps({"type": "THOUGHT", "content": content}) + "\n\n")
            if hasattr(step, 'thought') and step.thought:
                emit_thought(step.thought)
            elif hasattr(step, 'text') and step.text:
                emit_thought(step.text)
            elif isinstance(step, str):
                emit_thought(step)
            elif isinstance(step, tuple) and len(step) > 0:
                if hasattr(step[0][0], 'thought'):
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
        sre_agent=sre
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
                loop.call_soon_threadsafe(queue.put_nowait, "data: " + json.dumps({"type": "FINAL_RESPONSE", "content": res.final_response}) + "\n\n")
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, "data: " + json.dumps({"type": "FINAL_RESPONSE", "content": f"Error: {str(e)}"}) + "\n\n")
                loop.call_soon_threadsafe(queue.put_nowait, "data: [DONE]\n\n")


        while True:
            if chunk == "data: [DONE]\n\n":
                break
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")

    uvicorn.run(app, host="0.0.0.0", port=8000)
