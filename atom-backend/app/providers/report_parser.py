"""Key-free heuristic parser for the two PEIEX layouts.

Reads the obrigatorio fields straight from the report text:
- "Plano de Exportacao" (produto): SH6/NCM + "Mercado selecionado".
- "Mapa de Valor" (servico): NBS/CNAE + mercado prioritario.

An LLM parser (Bloco 5, needs a key) will supersede this for robustness; the
contract (ExtractedReport) stays the same.
"""
import re

from app.providers.base import ExtractedReport

# (regex, normalized label). Order matters: most specific first.
_COUNTRIES = [
    (r"estados\s+unidos|\bEUA\b|\bUSA\b", "EUA"),
    (r"paraguai", "Paraguai"),
    (r"m[eé]xico", "México"),
    (r"argentina", "Argentina"),
    (r"canad[aá]", "Canadá"),
    (r"uruguai", "Uruguai"),
    (r"col[oô]mbia", "Colômbia"),
    (r"\bchile\b", "Chile"),
    (r"\bperu\b", "Peru"),
    (r"equador", "Equador"),
    (r"\beuropa\b", "Europa"),
]

_NBS = re.compile(r"\b(\d\.\d{4}\.\d{2}\.\d{2})\b")
_CNAE = re.compile(r"\b(\d{2}\.\d{2}-\d-\d{2})\b")
_NCM = re.compile(r"\b(\d{4}\.\d{2}\.\d{2})\b")


def _find_country(scope: str) -> str | None:
    for pat, norm in _COUNTRIES:
        if re.search(pat, scope, re.IGNORECASE):
            return norm
    return None


def _market(texto: str) -> str | None:
    for anchor in (r"mercado\s+selecionado", r"mercado\s+priorit", r"mercado[-\s]alvo"):
        m = re.search(anchor, texto, re.IGNORECASE)
        if m:
            # Janela dos dois lados: o pais pode vir antes ("Mexico ... mercado
            # prioritario") ou depois ("Mercado selecionado: Paraguai") da ancora.
            lo = max(0, m.start() - 160)
            found = _find_country(texto[lo: m.start() + 240])
            if found:
                return found
    return None


class HeuristicReportParser:
    def parse(self, texto: str) -> ExtractedReport:
        is_servico = bool(
            re.search(r"\bNBS\b", texto)
            or re.search(r"mapa\s+de\s+valor", texto, re.IGNORECASE)
            or re.search(r"servi[cç]o\s+a\s+ser\s+exportado", texto, re.IGNORECASE)
        )
        tipo = "servico" if is_servico else "produto"

        if is_servico:
            codigo = (_NBS.search(texto) or _CNAE.search(texto))
        else:
            codigo = _NCM.search(texto)
        codigo_fiscal = codigo.group(1) if codigo else None

        desc = None
        m = re.search(
            r"Indica[cç][aã]o do produto a ser exportado[^:]*:\s*(.+)", texto, re.IGNORECASE
        )
        if m:
            desc = m.group(1).strip().split("\n")[0][:300]

        return ExtractedReport(
            tipo=tipo,
            codigo_fiscal=codigo_fiscal,
            produto_descricao=desc,
            mercado_sugerido=_market(texto),
            perfil_comprador=None,  # LLM parser preenche melhor (Bloco 5)
        )
