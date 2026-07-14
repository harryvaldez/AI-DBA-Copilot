"""AI DBA Copilot - Detection Engine Service"""

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="AI DBA Copilot - Detection Engine", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "detection-engine", "version": "0.1.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
