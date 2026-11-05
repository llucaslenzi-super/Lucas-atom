"""
Cliente da API EmpresAqui.

Formatos CONFIRMADOS empiricamente em 2026-11-05 (não é leitura de doc):

  CNPJ 14 dígitos  → objeto único, 41 chaves na raiz
  CNPJ  8 dígitos  → {cnpj_base, filtro_matriz_filial, quantidade, resultados:[...]}
                     cada item de resultados tem as mesmas 41 chaves

  Sócios vêm em CHAVES NUMÉRICAS ("0", "1", ...) no objeto, não em array.
  enrichment é um dict de 34 campos no plano Plus; null fora dele.

Limite: 1 requisição por segundo por token.
"""
from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterator

from . import config


# ──────────────────────────────────────────────────────────── CNPJ

def so_digitos(valor) -> str:
    return "".join(c for c in str(valor or "") if c.isdigit())


def dv_valido(cnpj: str) -> bool:
    """Valida os 2 dígitos verificadores (módulo 11). De graça, antes de gastar requisição."""
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    for tamanho in (12, 13):
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-tamanho:]
        soma = sum(int(d) * p for d, p in zip(cnpj[:tamanho], pesos))
        resto = soma % 11
        if int(cnpj[tamanho]) != (0 if resto < 2 else 11 - resto):
            return False
    return True


def normalizar(valor) -> tuple[str, str] | None:
    """
    Devolve (cnpj, modo) onde modo é 'completo' (14) ou 'base' (8).
    None se não for aproveitável. Não valida DV de base (base não tem DV).
    """
    d = so_digitos(valor)
    if len(d) == 14:
        return (d, "completo") if dv_valido(d) else None
    if len(d) == 8:
        return d, "base"
    if 8 < len(d) < 14:               # planilha comeu zero à esquerda
        d = d.zfill(14)
        return (d, "completo") if dv_valido(d) else None
    return None


# ──────────────────────────────────────────────────────────── achatamento

CAMPOS_ENRICHMENT = [
    "site_validado", "dominio_validado", "email_principal", "telefone_principal",
    "whatsapp_principal", "instagram_principal", "linkedin_principal",
    "facebook_principal", "emails_texto", "telefones_texto", "whatsapps_texto",
    "instagram_texto", "linkedin_texto", "facebook_texto", "google_maps_texto",
    "tem_site", "tem_email", "tem_telefone", "tem_whatsapp", "tem_instagram",
    "tem_linkedin", "tem_facebook", "qtd_emails", "qtd_telefones", "qtd_whatsapps",
    "qtd_instagram", "qtd_linkedin", "qtd_facebook", "score_site_match",
    "tags", "classificacao", "status", "fonte_atualizada_em",
]

QUALIFICACAO_DECISOR = ("ADMINISTRADOR", "PRESIDENTE", "DIRETOR")


def _data(v):
    """00000000 e vazio significam 'sem data'."""
    s = so_digitos(v)
    return None if not s or s == "00000000" else s


def _registros(resposta: dict) -> list[dict]:
    """Normaliza as duas formas de resposta numa lista de registros."""
    if not isinstance(resposta, dict):
        return []
    if "Erro" in resposta:
        return []
    if isinstance(resposta.get("resultados"), list):
        return [r for r in resposta["resultados"] if isinstance(r, dict)]
    return [resposta] if "cnpj" in resposta else []


def achatar(resposta: dict) -> list[dict]:
    """Um registro da API → uma linha plana, pronta pra CSV."""
    linhas = []
    for r in _registros(resposta):
        enr = r.get("enrichment") or {}
        if not isinstance(enr, dict):
            enr = {}

        # Sócios: chaves numéricas na raiz, não array.
        socios = [r[k] for k in sorted((k for k in r if k.isdigit()), key=int)
                  if isinstance(r[k], dict)]
        decisor = next(
            (s for s in socios
             if any(q in str(s.get("socios_qualificacao", "")).upper()
                    for q in QUALIFICACAO_DECISOR)),
            socios[0] if socios else {},
        )

        site = (r.get("site") or "").strip()
        if site and not site.startswith(("http://", "https://")):
            site = "https://" + site

        tel = lambda d, n: (f"{r.get(d) or ''}{r.get(n) or ''}").strip() or None

        linha = {
            "cnpj": r.get("cnpj"),
            "razao_social": r.get("razao"),
            "nome_fantasia": r.get("fantasia"),
            "situacao": config.SITUACAO.get(str(r.get("situacao_cadastral")), r.get("situacao_cadastral")),
            "matriz_filial": {"1": "MATRIZ", "2": "FILIAL"}.get(str(r.get("matriz")), None),
            "uf": r.get("log_uf"),
            "municipio": r.get("log_municipio"),
            "bairro": r.get("log_bairro"),
            "logradouro": " ".join(x for x in (r.get("log_tipo"), r.get("log_nome"), r.get("log_num")) if x),
            "complemento": " ".join((r.get("log_comp") or "").split()),  # vem com espaço duplo
            "cep": r.get("log_cep"),
            "cnae_principal": r.get("cnae_principal"),
            "cnae_secundario": r.get("cnae_secundario"),   # CSV, não array
            "natureza_juridica": r.get("natureza_juridica"),
            "porte": config.PORTE_API.get(str(r.get("porte")), r.get("porte")),
            "capital_social": r.get("capital_social"),
            "faturamento": r.get("faturamento"),
            "quadro_funcionarios": r.get("quadro_funcionarios"),
            "regime_tributario": r.get("regime_tributario"),
            "opcao_simples": r.get("opcao_simples"),
            "opcao_mei": r.get("opcao_mei"),
            "data_abertura": _data(r.get("data_abertura")),
            "data_situacao": _data(r.get("data_sit_cad")),
            "programas_especiais": "; ".join(r.get("programas_especiais") or []),
            "importa_exporta": any("IMPORTA" in str(p).upper()
                                   for p in (r.get("programas_especiais") or [])),
            # contato cadastral
            "telefone_1": tel("ddd_1", "tel_1"),
            "telefone_2": tel("ddd_2", "tel_2"),
            "email": r.get("email"),
            "site": site or None,
            # decisor
            "socio_admin": decisor.get("socios_nome"),
            "socio_admin_qualificacao": decisor.get("socios_qualificacao"),
            "socio_admin_entrada": _data(decisor.get("socios_entrada")),
            "qtd_socios": len(socios),
            # dívidas
            "qtd_dividas": sum(
                1 for d in (r.get("historicoDividasPorTrimestre") or [])
                if isinstance(d, dict) and "NAO POSSUI" not in str(d.get("valor", "")).upper()
            ),
        }
        for c in CAMPOS_ENRICHMENT:
            linha[f"enr_{c}"] = enr.get(c)

        # Procedência por campo — exigência de auditoria/LGPD.
        linha["fonte_telefone"] = ("empresaqui_enrichment" if enr.get("telefone_principal")
                                   else "receita_cadastral" if linha["telefone_1"] else None)
        linha["fonte_email"] = ("empresaqui_enrichment" if enr.get("email_principal")
                                else "receita_cadastral" if linha["email"] else None)
        linha["fonte_whatsapp"] = "empresaqui_enrichment" if enr.get("whatsapp_principal") else None
        linhas.append(linha)
    return linhas


# ──────────────────────────────────────────────────────────── cliente

class TokenInvalido(RuntimeError):
    pass


@dataclass
class Resultado:
    cnpj: str
    http: int
    dados: dict | None
    do_cache: bool


class EmpresAqui:
    """1 req/s, cache permanente em SQLite, retomada automática."""

    def __init__(self, token: str | None = None, cache=None, intervalo: float | None = None):
        self.token = (token or config.TOKEN).strip()
        if not self.token:
            raise TokenInvalido("Defina EMPRESAQUI_TOKEN no ambiente.")
        self.intervalo = intervalo if intervalo is not None else config.INTERVALO_SEG
        self._ultima = 0.0
        self.db = sqlite3.connect(str(cache or config.CACHE))
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            " cnpj TEXT PRIMARY KEY, http INTEGER, json TEXT, ts TEXT)"
        )
        self.db.commit()

    # -------------------------------------------------- cache
    def _do_cache(self, cnpj: str):
        r = self.db.execute("SELECT http, json FROM cache WHERE cnpj=?", (cnpj,)).fetchone()
        if not r:
            return None
        return r[0], (json.loads(r[1]) if r[1] else None)

    def _guardar(self, cnpj: str, http: int, dados):
        self.db.execute(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?,datetime('now'))",
            (cnpj, http, json.dumps(dados, ensure_ascii=False) if dados else None),
        )
        self.db.commit()

    # -------------------------------------------------- rede
    def _esperar(self):
        falta = self.intervalo - (time.monotonic() - self._ultima)
        if falta > 0:
            time.sleep(falta)
        self._ultima = time.monotonic()

    def _buscar(self, cnpj: str) -> tuple[int, dict | None]:
        url = config.ENDPOINT + "?" + urllib.parse.urlencode({"Token": self.token, "Cnpj": cnpj})
        for tentativa in range(5):
            self._esperar()
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
            except urllib.error.HTTPError as e:
                corpo = e.read().decode("utf-8", "replace")[:300]
                if e.code in (401, 403):
                    raise TokenInvalido(f"HTTP {e.code}: {corpo}")
                if e.code == 404:
                    return 404, None
                if e.code == 429 or e.code >= 500:
                    time.sleep(2 ** tentativa)       # 1,2,4,8,16s
                    continue
                return e.code, None
            except Exception:
                time.sleep(2 ** tentativa)
        return 0, None

    # -------------------------------------------------- público
    def consultar(self, cnpj: str, revalidar=False) -> Resultado:
        em_cache = None if revalidar else self._do_cache(cnpj)
        if em_cache is not None:
            return Resultado(cnpj, em_cache[0], em_cache[1], True)
        http, dados = self._buscar(cnpj)
        self._guardar(cnpj, http, dados)
        return Resultado(cnpj, http, dados, False)

    def consultar_lote(self, cnpjs, revalidar=False) -> Iterator[Resultado]:
        vistos = set()
        for c in cnpjs:
            n = normalizar(c)
            if not n or n[0] in vistos:
                continue
            vistos.add(n[0])
            yield self.consultar(n[0], revalidar)

    def estatisticas(self) -> dict:
        q = lambda s: self.db.execute(s).fetchone()[0]
        return {
            "em_cache": q("SELECT COUNT(*) FROM cache"),
            "ok": q("SELECT COUNT(*) FROM cache WHERE http=200"),
            "nao_encontrados": q("SELECT COUNT(*) FROM cache WHERE http=404"),
        }
