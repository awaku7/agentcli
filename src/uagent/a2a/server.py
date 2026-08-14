from __future__ import annotations

import argparse
import asyncio
import json
from contextvars import copy_context
from typing import Any, AsyncIterator, Optional
from uuid import uuid4

try:
    import uvicorn
except ImportError:
    from .._pip_auto import install_with_status as _install_uv

    _install_uv("uvicorn")
    import uvicorn

try:
    from fastapi import Depends, FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError:
    from .._pip_auto import install_with_status as _install_fa

    _install_fa("fastapi")
    from fastapi import Depends, FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse

from ..env_utils import env_get
from ..auth import CredentialStore, get_default_credential_store
from ..i18n import (
    _,
    detect_lang,
    reset_contextvar_locale,
    set_contextvar_locale,
)
from ..runtime.runtime_init import reload_dotenv_custom
from ..runtime.runtime_env import validate_or_exit_startup_env
from ..runtime.logging_setup import bind_event_context, log_event, reset_event_context
from .auth import require_bearer_auth
from .engine import run_once
from .errors import A2AHttpError, aip193_error
from .models import (
    ListTasksResponse,
    SendMessageRequest,
    SendMessageResponse,
    task_to_model,
)
from .task_store import (
    InMemoryTaskStore,
    SQLiteTaskStore,
    TaskRecord,
    TaskRuntime,
    TaskStatus,
)
from ..runtime.execution import lifecycle_execution
from ..runtime.lifecycle import InvalidLifecycleTransition


def _bool_env(name: str, default: bool = False) -> bool:
    v = (env_get(name, "") or "").strip().lower()
    if not v:
        return bool(default)
    return v in ("1", "true", "yes", "on")


def _lifecycle_transition(runtime: TaskRuntime | None, method: str) -> None:
    if runtime is None:
        return
    try:
        getattr(runtime.lifecycle, method)()
    except InvalidLifecycleTransition:
        # Task cancellation and worker completion race by design. The task store
        # remains authoritative when a terminal transition already happened.
        pass


def _build_task_store() -> InMemoryTaskStore | SQLiteTaskStore:
    backend = (env_get("UAGENT_TASK_STORE", "memory") or "memory").strip().lower()
    if backend == "sqlite":
        path = env_get("UAGENT_TASK_STORE_PATH", "") or ""
        if not path:
            from ..utils.paths import get_state_dir

            path = str(get_state_dir() / "a2a" / "tasks.sqlite3")
        return SQLiteTaskStore(path)
    if backend not in {"memory", "inmemory"}:
        raise ValueError(f"unsupported UAGENT_TASK_STORE backend: {backend}")
    return InMemoryTaskStore()


def build_app(*, credential_store: CredentialStore | None = None) -> FastAPI:
    app = FastAPI(title=_("uagent A2A"))
    app.state.credential_store = credential_store or get_default_credential_store()

    store = _build_task_store()
    try:
        recovered = store.recover_incomplete()
    except AttributeError:
        recovered = []
    if recovered:
        log_event("task.recovered_after_restart", count=len(recovered), status="failed")
    from ..tools import configure_default_confirmation

    configure_default_confirmation()
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
    async def agent_card() -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        # Future: include tools, capabilities, extensions.
        return {
            "name": "uagent",
            "capabilities": {
                "tools": True,
                "streaming": True,
            },
        }

    async def _execute_task(task_id: str, user_text: str) -> None:
        runtime = store.runtime(task_id)
        event_token = bind_event_context(task_id=task_id, correlation_id=task_id)
        locale_token = set_contextvar_locale(runtime.locale if runtime else detect_lang())
        try:
            async with sem:
                if runtime and runtime.cancel_event and runtime.cancel_event.is_set():
                    _lifecycle_transition(runtime, "cancel")
                    store.transition(task_id, TaskStatus.CANCEL_REQUESTED.value, TaskStatus.CANCELLED.value)
                    return
                _lifecycle_transition(runtime, "start")
                try:
                    with lifecycle_execution(runtime.lifecycle):
                        ctx = copy_context()
                        assistant_msg, err = await asyncio.to_thread(
                            ctx.run, run_once, user_text=user_text
                        )
                except asyncio.CancelledError:
                    _lifecycle_transition(runtime, "cancel")
                    store.transition(
                        task_id,
                        (TaskStatus.IN_PROGRESS.value, TaskStatus.CANCEL_REQUESTED.value),
                        TaskStatus.CANCELLED.value,
                    )
                    raise
                except Exception as exc:
                    _lifecycle_transition(runtime, "fail")
                    store.transition(
                        task_id,
                        TaskStatus.IN_PROGRESS.value,
                        TaskStatus.FAILED.value,
                        error={"code": "INTERNAL", "message": str(exc)},
                    )
                    return
                if err:
                    _lifecycle_transition(runtime, "fail")
                    store.transition(
                        task_id,
                        TaskStatus.IN_PROGRESS.value,
                        TaskStatus.FAILED.value,
                        error=err,
                    )
                    return
                _lifecycle_transition(runtime, "complete")
                store.transition(
                    task_id,
                    TaskStatus.IN_PROGRESS.value,
                    TaskStatus.SUCCEEDED.value,
                    output_message=assistant_msg,
                )
        finally:
            reset_contextvar_locale(locale_token)
            reset_event_context(event_token)

    @app.post("/message:send", response_model=SendMessageResponse)
    async def message_send(
        req: SendMessageRequest,
        request: Request,
        _auth: Any = Depends(require_bearer_auth),
    ) -> SendMessageResponse:
        user_text = str(req.message.content or "")
        task_id = str(uuid4())
        rec = TaskRecord(id=task_id, input_message=req.message.model_dump())
        store.create(rec)
        log_event("a2a.task.created", task_id=task_id, locale=request.headers.get("accept-language", ""))

        runtime = TaskRuntime(
            cancel_event=asyncio.Event(),
            locale=(request.headers.get("accept-language", "").split(",")[0] or detect_lang()),
        )
        store.register_runtime(task_id, runtime)

        # Execute synchronously unless returnImmediately is true.
        if bool(req.returnImmediately):
            runtime.asyncio_task = asyncio.create_task(_execute_task(task_id, user_text))
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
            def _emit(obj: dict[str, Any]) -> bytes:
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
        if rec.status in (
            TaskStatus.SUCCEEDED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        ):
            return {"task": task_to_model(rec).model_dump()}

        runtime = store.runtime(task_id)
        requested = store.transition(
            task_id,
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.CANCEL_REQUESTED.value,
        )
        if requested is not None and runtime:
            _lifecycle_transition(runtime, "cancel")
            if runtime.cancel_event:
                runtime.cancel_event.set()
            if runtime.asyncio_task and not runtime.asyncio_task.done():
                runtime.asyncio_task.cancel()
            store.transition(
                task_id,
                TaskStatus.CANCEL_REQUESTED.value,
                TaskStatus.CANCELLED.value,
            )
        rec2 = store.get(task_id)
        return {"task": task_to_model(rec2).model_dump()}  # type: ignore[arg-type]

    @app.post("/tasks/{task_id}:subscribe")
    async def subscribe_task(
        task_id: str,
        _auth: Any = Depends(require_bearer_auth),
    ):
        # SSE: poll task state until terminal.
        async def gen() -> AsyncIterator[bytes]:
            def _emit(obj: dict[str, Any]) -> bytes:
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
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
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
    parser.add_argument(
        "--tool-genre-mask",
        type=int,
        default=None,
        help=_(
            "Tool genre bitmask (1=comm,2=office,4=devel,8=iot,16=exec,32=external,64=media,127=all). Skips the interactive genre prompt when specified."
        ),
    )
    parser.add_argument(
        "--use-tool",
        dest="use_tool",
        action="store_true",
        default=None,
        help=_("Enable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )
    parser.add_argument(
        "--no-use-tool",
        dest="use_tool",
        action="store_false",
        default=None,
        help=_("Disable tool sending to LLM (overrides UAGENT_USE_TOOL env var)."),
    )

    args = parser.parse_args(argv)

    # Keep env in sync with runtime arguments (helps agent card URL calculation).
    try:
        import os

        os.environ["UAGENT_A2A_HOST"] = str(args.host)
        os.environ["UAGENT_A2A_PORT"] = str(args.port)
    except Exception:
        pass

    reload_dotenv_custom()
    validate_or_exit_startup_env(context="a2a")

    # Tool genre selection (same dialog as CLI startup)
    try:
        from ..cli_startup import (
            _apply_startup_tool_genre_mask,
        )

        if args.tool_genre_mask is not None:
            _apply_startup_tool_genre_mask(args.tool_genre_mask)
        else:
            # Default: basic only
            _apply_startup_tool_genre_mask(0)
    except Exception:
        pass

    # Initialize runtime tools_enabled flag.
    # Priority: --use-tool / --no-use-tool CLI arg > UAGENT_USE_TOOL env var > default ON.
    try:
        from .. import core as _core_module

        _use_tool_arg = getattr(args, "use_tool", None)
        if _use_tool_arg is not None:
            _core_module.tools_enabled = bool(_use_tool_arg)
        else:
            _use_tool_env = (env_get("UAGENT_USE_TOOL") or "").strip().lower()
            _core_module.tools_enabled = _use_tool_env not in (
                "0",
                "false",
                "no",
                "off",
            )
    except Exception:
        pass

    app = build_app()
    uvicorn.run(app, host=str(args.host), port=int(args.port), reload=bool(args.reload))


if __name__ == "__main__":
    main()
