from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str
    senha: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class AccessOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ConsultaIn(BaseModel):
    relatorio_id: UUID | None = None
    tipo: Literal["produto", "servico"] = "produto"
    produto_descricao: str | None = None
    codigo_fiscal: str | None = None
    paises: list[str] = Field(default_factory=list)
    perfil_comprador: str | None = None
    plano: Literal["padrao", "premium"] = "padrao"
    leads_solicitados: int = Field(gt=0, le=350)


class ConsultaOut(BaseModel):
    id: UUID
    status: str
    leads_solicitados: int
    leads_entregues: int
    plano: str


class LeadOut(BaseModel):
    id: UUID
    empresa_nome: str | None = None
    pais: str | None = None
    cidade: str | None = None
    tipo_negocio: str | None = None
    telefone: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    instagram: str | None = None
    score: float | None = None
