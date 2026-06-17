import asyncio
import logging
import os
import time
from typing import Dict

import httpx
import uvicorn
from fastapi import FastAPI, Request
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse

UPSTREAM = os.environ.get("NIM_GUARD_UPSTREAM", "http://127.0.0.1:4001")
COOLDOWN_SECONDS = float(os.environ.get("NIM_GUARD_429_COOLDOWN", "65"))
MIN_GAP_SECONDS = float(os.environ.get("NIM_GUARD_MIN_GAP", "1.7"))
MAX_429_RETRIES = int(os.environ.get("NIM_GUARD_MAX_429_RETRIES", "1"))

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "host",
}

app = FastAPI()
client = httpx.AsyncClient(timeout=None)

gate_lock = asyncio.Lock()
cooldown_until = 0.0
next_allowed_at = 0.0


def filtered_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }


def is_probably_rate_limit(status_code: int, body: bytes) -> bool:
    if status_code == 429:
        return True

    text = body[:3000].decode("utf-8", errors="ignore").lower()

    return (
        "too many requests" in text
        or "rate limit" in text
        or "ratelimiterror" in text
        or "nvidia_nimexception" in text and "429" in text
    )


async def reserve_upstream_slot() -> None:
    global next_allowed_at

    while True:
        async with gate_lock:
            now = time.monotonic()
            wait_for = max(
                cooldown_until - now,
                next_allowed_at - now,
                0,
            )

            if wait_for <= 0:
                next_allowed_at = time.monotonic() + MIN_GAP_SECONDS
                return

        logging.warning("NIM guard segurando request por %.1fs", wait_for)
        await asyncio.sleep(wait_for)


async def start_429_cooldown() -> None:
    global cooldown_until

    async with gate_lock:
        now = time.monotonic()
        cooldown_until = max(cooldown_until, now + COOLDOWN_SECONDS)

    logging.warning("429 detectado. Cooldown ativado por %.1fs", COOLDOWN_SECONDS)


async def forward_once(request: Request, body: bytes) -> httpx.Response:
    path = request.url.path
    query = request.url.query

    url = f"{UPSTREAM}{path}"
    if query:
        url = f"{url}?{query}"

    headers = filtered_headers(dict(request.headers))

    await reserve_upstream_slot()

    upstream_request = client.build_request(
        method=request.method,
        url=url,
        headers=headers,
        content=body,
    )

    return await client.send(upstream_request, stream=True)


@app.get("/__nim_guard_status")
async def guard_status():
    now = time.monotonic()
    remaining = max(cooldown_until - now, 0)

    return JSONResponse(
        {
            "status": "ok",
            "upstream": UPSTREAM,
            "cooldown_remaining_seconds": round(remaining, 1),
            "min_gap_seconds": MIN_GAP_SECONDS,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "max_429_retries": MAX_429_RETRIES,
        }
    )


@app.api_route("/", methods=["GET", "HEAD"])
async def root_healthcheck():
    return Response(status_code=200)


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(path: str, request: Request):
    body = await request.body()
    attempt = 0

    while True:
        response = await forward_once(request, body)

        if response.status_code >= 400:
            error_body = await response.aread()
            await response.aclose()

            if is_probably_rate_limit(response.status_code, error_body):
                await start_429_cooldown()

                if attempt < MAX_429_RETRIES:
                    attempt += 1
                    logging.warning(
                        "Upstream retornou rate limit. Esperando %.1fs e tentando a mesma request de novo.",
                        COOLDOWN_SECONDS,
                    )
                    await asyncio.sleep(COOLDOWN_SECONDS)
                    continue

                return PlainTextResponse(
                    "NVIDIA NIM rate limit hit. Local guard activated cooldown. Try again after about 1 minute.",
                    status_code=429,
                    headers={"Retry-After": str(int(COOLDOWN_SECONDS))},
                )

            if response.status_code in {500, 502, 503, 504} and attempt < 2:
                attempt += 1
                delay = 5 * attempt

                logging.warning(
                    "Upstream retornou %s. Retry em %ss. Preview: %s",
                    response.status_code,
                    delay,
                    error_body[:300].decode("utf-8", errors="ignore"),
                )

                await asyncio.sleep(delay)
                continue

            return Response(
                content=error_body,
                status_code=response.status_code,
                headers=filtered_headers(dict(response.headers)),
                media_type=response.headers.get("content-type"),
            )

        return StreamingResponse(
            response.aiter_raw(),
            status_code=response.status_code,
            headers=filtered_headers(dict(response.headers)),
            background=BackgroundTask(response.aclose),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    host = os.environ.get("NIM_GUARD_HOST", "127.0.0.1")
    port = int(os.environ.get("NIM_GUARD_PORT", "4000"))

    uvicorn.run(app, host=host, port=port)
