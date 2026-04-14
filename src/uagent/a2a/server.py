from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, AsyncIterator, Dict, Optional
from uuid import uuid4

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..env_utils import env_get
from .auth import require_bearer_auth
from .engine import run_once
from .errors import A2AHttpError, aip193_error
from .models import (
    ListTasksResponse,
    SendMessageRequest,
    SendMessageResponse,
    task_to_model,
)
from .task_store import InMemoryTaskStore, TaskRecord


def _bool_env(name: str, default: bool = False) -> bool:
    v = (env_get(name, "") or "").strip().lower()
    if not v:
        return bool(default)
    return v in ("1", "true", "yes", "on")


def build_app() -> FastAPI:
    app = FastAPI(title="uagent A2A")

    store = InMemoryTaskStore()
    sem = asyncio.Semaphore(int(env_get("UAGENT_A2A_CONCURRENCY", "1") or "1"))

    @app.exception_handler(A2AHttpError)
    async def _handle_a2a_http_error(_req: Request, exc: A2AHttpError):
        return JSONResponse(
            status_code=exc.status_code,
            content=aip193_error(
                code=exc.code, message=exc.message, details=exc.details
            ),
        )

    @app.get("/.well-known/agent-card.json")
    async def agent_card() -> Dict[str, Any]:
        # Best-effort card. Extended fields can be added later.
        base_url = (env_get("UAGENT_A2A_PUBLIC_BASE_URL", "") or "").strip()
        if not base_url:
            host = (env_get("UAGENT_A2A_HOST", "0.0.0.0") or "0.0.0.0").strip()
            port = int(env_get("UAGENT_A2A_PORT", "8765") or "8765")
            # When host is 0.0.0.0, a client typically uses localhost/real host.
            hint_host = "127.0.0.1" if host == "0.0.0.0" else host
            base_url = f"http://{hint_host}:{port}"

        return {
            "name": "uagent",
            "description": "uagent A2A server",
            "version": "0.1",
            "endpoints": {
                "sendMessage": f"{base_url}/message:send",
                "streamMessage": f"{base_url}/message:stream",
                "getTask": f"{base_url}/tasks/{{id}}",
                "listTasks": f"{base_url}/tasks",
                "cancelTask": f"{base_url}/tasks/{{id}}:cancel",
                "subscribeTask": f"{base_url}/tasks/{{id}}:subscribe",
                "extendedAgentCard": f"{base_url}/extendedAgentCard",
            },
            "authentication": {
                "type": "bearer",
                "tokenEnv": "UAGENT_A2A_TOKEN",
            },
        }

    @app.get("/extendedAgentCard")
    async def extended_agent_card(
        _auth: Any = Depends(require_bearer_auth),
    ) -> Dict[str, Any]:
        # Future: include tools, capabilities, extensions.
        return {
            "name": "uagent",
            "capabilities": {
                "tools": True,
                "streaming": True,
            },
        }

    async def _execute_task(task_id: str, user_text: str) -> None:
        async with sem:
            assistant_msg, err = run_once(user_text=user_text)
            if err:
                store.update(task_id, status="FAILED", error=err)
                return
            store.update(
                task_id,
                status="SUCCEEDED",
                output_message=assistant_msg,
            )

    @app.post("/message:send", response_model=SendMessageResponse)
    async def message_send(
        req: SendMessageRequest,
        _auth: Any = Depends(require_bearer_auth),
    ) -> SendMessageResponse:
        user_text = str(req.message.content or "")
        task_id = str(uuid4())
        rec = TaskRecord(id=task_id, input_message=req.message.model_dump())
        store.create(rec)

        # Execute synchronously unless returnImmediately is true.
        if bool(req.returnImmediately):
            asyncio.create_task(_execute_task(task_id, user_text))
            return SendMessageResponse(task=task_to_model(store.get(task_id)))  # type: ignore[arg-type]

        await _execute_task(task_id, user_text)
        r = store.get(task_id)
        if not r:
            raise A2AHttpError(status_code=500, code="INTERNAL", message="Task missing")
        return SendMessageResponse(task=task_to_model(r))

    @app.post("/message:stream")
    async def message_stream(
        req: SendMessageRequest,
        _auth: Any = Depends(require_bearer_auth),
    ):
        # SSE stream: emit a few lifecycle events.
        user_text = str(req.message.content or "")
        task_id = str(uuid4())
        rec = TaskRecord(id=task_id, input_message=req.message.model_dump())
        store.create(rec)

        async def gen() -> AsyncIterator[bytes]:
            def _emit(obj: Dict[str, Any]) -> bytes:
                return ("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode(
                    "utf-8"
                )

            yield _emit({"type": "task", "task": task_to_model(rec).model_dump()})
            yield _emit({"type": "status", "id": task_id, "status": "IN_PROGRESS"})

            await _execute_task(task_id, user_text)
            r = store.get(task_id)
            if not r:
                yield _emit(
                    {
                        "type": "error",
                        "error": {"code": "INTERNAL", "message": "Task missing"},
                    }
                )
                return

            yield _emit({"type": "task", "task": task_to_model(r).model_dump()})

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/tasks/{task_id}")
    async def get_task(
        task_id: str,
        _auth: Any = Depends(require_bearer_auth),
    ):
        rec = store.get(task_id)
        if not rec:
            raise A2AHttpError(
                status_code=404, code="NOT_FOUND", message="Task not found"
            )
        return {"task": task_to_model(rec).model_dump()}

    @app.get("/tasks", response_model=ListTasksResponse)
    async def list_tasks(
        limit: int = 100,
        offset: int = 0,
        _auth: Any = Depends(require_bearer_auth),
    ) -> ListTasksResponse:
        items = store.list(limit=min(int(limit), 500), offset=max(int(offset), 0))
        return ListTasksResponse(tasks=[task_to_model(t) for t in items])

    @app.post("/tasks/{task_id}:cancel")
    async def cancel_task(
        task_id: str,
        _auth: Any = Depends(require_bearer_auth),
    ):
        rec = store.get(task_id)
        if not rec:
            raise A2AHttpError(
                status_code=404, code="NOT_FOUND", message="Task not found"
            )
        # Best-effort: we do not interrupt in-flight execution yet.
        store.update(task_id, status="CANCELLED")
        rec2 = store.get(task_id)
        return {"task": task_to_model(rec2).model_dump()}  # type: ignore[arg-type]

    @app.post("/tasks/{task_id}:subscribe")
    async def subscribe_task(
        task_id: str,
        _auth: Any = Depends(require_bearer_auth),
    ):
        # SSE: poll task state until terminal.
        async def gen() -> AsyncIterator[bytes]:
            def _emit(obj: Dict[str, Any]) -> bytes:
                return ("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode(
                    "utf-8"
                )

            terminal = {"SUCCEEDED", "FAILED", "CANCELLED"}
            while True:
                rec = store.get(task_id)
                if not rec:
                    yield _emit(
                        {
                            "type": "error",
                            "error": {"code": "NOT_FOUND", "message": "Task not found"},
                        }
                    )
                    return

                yield _emit({"type": "task", "task": task_to_model(rec).model_dump()})
                if rec.status in terminal:
                    return
                await asyncio.sleep(0.25)

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="uaga", add_help=True)
    parser.add_argument(
        "--host",
        default=(env_get("UAGENT_A2A_HOST", "0.0.0.0") or "0.0.0.0"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(env_get("UAGENT_A2A_PORT", "8765") or "8765"),
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=_bool_env("UAGENT_A2A_RELOAD", False),
    )

    args = parser.parse_args(argv)

    # Keep env in sync with runtime arguments (helps agent card URL calculation).
    try:
        import os

        os.environ['PYTHONHTTPSVERIFY'] = '0'
        os.environ["UAGENT_A2A_HOST"] = str(args.host)
        os.environ["UAGENT_A2A_PORT"] = str(args.port)
    except Exception:
        pass

    app = build_app()
    uvicorn.run(app, host=str(args.host), port=int(args.port), reload=bool(args.reload))


if __name__ == "__main__":
    main()
