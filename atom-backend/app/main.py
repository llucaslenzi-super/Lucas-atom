from fastapi import FastAPI

from app.routers import auth, consultas

app = FastAPI(title="Atom - Agente de Prospeccao de Exportacao", version="0.1.0")

app.include_router(auth.router)
app.include_router(consultas.router)


@app.get("/v1/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
