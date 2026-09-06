#!/usr/bin/env python3
import sys
import json
import argparse
from uuid import uuid4
import os

def emit(typ: str, content: str):
    print(json.dumps({"type": typ, "content": content}), flush=True)

def step_callback(step):
    try:
        if hasattr(step, 'thought') and step.thought:
            emit("THOUGHT", step.thought)
        elif hasattr(step, 'text') and step.text:
            emit("THOUGHT", step.text)
        elif isinstance(step, str):
            emit("THOUGHT", step)
        elif isinstance(step, tuple) and len(step) > 0:
            if hasattr(step[0][0], 'thought'):
                emit("THOUGHT", step[0][0].thought)
            elif isinstance(step[0][0], str):
                emit("THOUGHT", step[0][0])
            else:
                emit("THOUGHT", str(step))
        else:
            emit("THOUGHT", str(step))
    except Exception as e:
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, required=True)
    parser.add_argument("--team", type=str, default="data-platform")
    args = parser.parse_args()

    sys.stdout.reconfigure(line_buffering=True)
    original_stdout = sys.stdout
    
    import io
    sys.stdout = io.StringIO()
    
    try:
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

        finops = create_finops_agent(step_callback=step_callback, verbose=False)
        sre = create_sre_agent(step_callback=step_callback, verbose=False)

        flow = FinOpsFlow(
            memory_repo=memory_repo,
            finops_agent=finops,
            sre_agent=sre
        )
        
        sys.stdout = original_stdout
        emit("THOUGHT", "Analyzing your query and context...")
        sys.stdout = io.StringIO()
        
        result = flow.execute_flow(
            query=args.query,
            session_id=str(uuid4()),
            team_scope=args.team,
        )
        
        sys.stdout = original_stdout
        emit("FINAL_RESPONSE", result.final_response)
        
    except Exception as e:
        sys.stdout = original_stdout
        emit("FINAL_RESPONSE", f"Error evaluating: {str(e)}")

if __name__ == "__main__":
    main()
