"""
Mock API Server — Simulates transient failure scenarios.

Endpoints:
  /api/data      → 429 Too Many Requests (rate limit)
  /api/service   → 503 Service Unavailable
  /api/gateway   → 504 Gateway Timeout
  /api/slow      → Sleeps 30s, causing client-side timeout
  /health        → 200 OK
"""

import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Partner Data API (Mock)")


@app.get("/api/data")
async def get_data():
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too Many Requests",
            "message": "Rate limit exceeded. Please retry after backoff.",
            "retry_after": 5,
        },
        headers={"Retry-After": "5"},
    )


@app.get("/api/service")
async def service_unavailable():
    return JSONResponse(
        status_code=503,
        content={
            "error": "Service Unavailable",
            "message": "The service is temporarily unavailable. Please try again later.",
        },
    )


@app.get("/api/gateway")
async def gateway_timeout():
    return JSONResponse(
        status_code=504,
        content={
            "error": "Gateway Timeout",
            "message": "The upstream server did not respond in time.",
        },
    )


@app.get("/api/slow")
async def slow_endpoint():
    """Sleeps long enough to trigger a client-side read timeout."""
    await asyncio.sleep(30)
    return {"data": "you should never see this"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8429)
