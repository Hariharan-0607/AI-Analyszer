from fastapi import FastAPI

from app.routes import todos

app = FastAPI(title="Todo API", version="1.0.0")
app.include_router(todos.router, prefix="/todos", tags=["todos"])


@app.get("/health")
def health():
    return {"status": "ok"}
