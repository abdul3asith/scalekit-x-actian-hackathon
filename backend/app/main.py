from app.api.health import router as health_router
from fastapi import FastAPI

app = FastAPI(title="Security Voice Agent API")

app.include_router(health_router)


@app.get("/")
def root():
    return {"status": "running"}
