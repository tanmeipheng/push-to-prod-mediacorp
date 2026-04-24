"""
Mock API Server — Simulates a rate-limiting partner API.
Hardcoded to return HTTP 429 Too Many Requests on every call.
"""

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


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8429)
