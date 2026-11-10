"""Provider contracts + data shapes shared by mock and real implementations.

Methods return ``(resultado, custo_usd)`` so the pipeline can enforce the cost
guardrail (PIPELINE.md) regardless of which implementation runs.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ExtractedReport:
    tipo: str = "produto"  # produto | servico
    codigo_fiscal: str | None = None  # NCM (produto) ou NBS (servico)
    produto_descricao: str | None = None
    mercado_sugerido: str | None = None
    perfil_comprador: str | None = None


@dataclass
class EmpresaAlvo:
    empresa: str
    cidade: str | None = None
    site: str | None = None
    contato: str | None = None


@dataclass
class LeadLimpo:
    empresa_nome: str
    pais: str | None = None
    cidade: str | None = None
    tipo_negocio: str | None = None
    site: str | None = None
    telefone: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    instagram: str | None = None
    decisor: dict = field(default_factory=dict)
    score: float = 0.0
    racional: str = ""
    fontes: dict = field(default_factory=dict)


class ReportParser(Protocol):
    def parse(self, texto: str) -> ExtractedReport: ...


class Discovery(Protocol):
    def descobrir(
        self, produto: str, mercado: str, perfil: str, n: int
    ) -> tuple[list[EmpresaAlvo], float]: ...


class Enrichment(Protocol):
    def enriquecer(
        self, empresas: list[EmpresaAlvo], pais: str
    ) -> tuple[list[dict], float]: ...


class Cleaner(Protocol):
    def limpar(
        self, brutos: list[dict], produto: str, perfil: str, alvo: int
    ) -> tuple[list[LeadLimpo], float]: ...
