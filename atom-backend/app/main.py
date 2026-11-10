from fastapi import FastAPI

from app.routers import auth, consultas, internal, relatorios

app = FastAPI(title="Atom - Agente de Prospeccao de Exportacao", version="0.1.0")

app.include_router(auth.router)
app.include_router(relatorios.router)
app.include_router(consultas.router)
app.include_router(internal.router)


@app.get("/v1/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
