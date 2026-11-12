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
import re
import sqlite3
import time
import urllib.error
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


def _digitos(v):
    return "".join(c for c in str(v or "") if c.isdigit())


def _handle_ig(v):
    """URL ou handle cru → @handle. Vale para o que o Maps e o IG devolvem."""
    if not v:
        return None
    s = str(v).strip().rstrip("/")
    if "instagram.com" in s:
        s = s.split("instagram.com/")[-1].split("/")[0].split("?")[0]
    s = s.lstrip("@").strip()
    return "@" + s if s else None


# Os campos *_texto do enrichment separam por " | ", não por vírgula.
# Medido: 7 e-mails, 3 telefones, 2 whatsapps e 2 instagrams com pipe.
# Tratar como vírgula transformava quatro e-mails numa string só.
_SEPARADORES = re.compile(r"[|,;\n]")

# Lixo que a própria fonte entrega. Não é invenção nossa descartar:
# u002f é uma barra escapada que vazou para dentro do endereço.
_EMAIL_LIXO = re.compile(r"^(exemplo|example|teste|test|email|seu)@|u002f", re.I)
_EMAIL_OK = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)


def _lista(*fontes):
    """Achata, limpa e desduplica preservando a ordem de chegada."""
    out = []
    for f in fontes:
        if f in (None, "", []):
            continue
        itens = f if isinstance(f, (list, tuple, set)) else _SEPARADORES.split(str(f))
        for v in itens:
            v = str(v).strip()
            if v and v not in out:
                out.append(v)
    return out


def _emails_validos(valores):
    """Formato válido e sem os marcadores de exemplo da fonte."""
    return [v for v in valores if _EMAIL_OK.match(v) and not _EMAIL_LIXO.search(v)]


def achatar(resposta: dict) -> list[dict]:
    """Um registro da API → uma linha com as 78 colunas de cnpj.colunas."""
    from datetime import date
    linhas = []
    for r in _registros(resposta):
        enr = r.get("enrichment") or {}
        if not isinstance(enr, dict):
            enr = {}

        # Chaves numéricas da raiz guardam DUAS coisas misturadas: sócios e
        # dívidas ativas. Medido em 61 empresas: 11 delas (18%) tinham registro
        # de dívida entre os sócios. Separar pelo campo que cada uma carrega.
        numericas = [r[k] for k in sorted((k for k in r if k.isdigit()), key=int)
                     if isinstance(r[k], dict)]
        socios = [d for d in numericas if d.get("socios_nome")]
        dividas = [d for d in numericas if d.get("dividas_numero")]

        # ---------- contato: TUDO junto, uma coluna por canal ----------
        # Fixo e WhatsApp na MESMA coluna: não há como saber qual número tem
        # WhatsApp, e separar seria inventar informação.
        contatos = _lista(
            _digitos(f"{r.get('ddd_1') or ''}{r.get('tel_1') or ''}") or None,
            _digitos(f"{r.get('ddd_2') or ''}{r.get('tel_2') or ''}") or None,
            [_digitos(x) for x in _lista(enr.get("telefone_principal"),
                                         enr.get("telefones_texto"),
                                         enr.get("whatsapp_principal"),
                                         enr.get("whatsapps_texto"))],
        )
        emails = _emails_validos([e.lower() for e in _lista(
            r.get("email"), enr.get("email_principal"), enr.get("emails_texto"))])
        instas = _lista([_handle_ig(x) for x in
                         _lista(enr.get("instagram_principal"), enr.get("instagram_texto"))])
        sites = _lista(_url(r.get("site")), _url(enr.get("site_validado")))

        prog = r.get("programas_especiais") or []
        temp = lambda alvo: any(alvo in str(p).upper() for p in prog)
        abertura = _data(r.get("data_abertura"))

        linha = {
            # ---------- núcleo (ordem definida pelo cliente) ----------
            "cnpj": r.get("cnpj"),
            "razao_social": r.get("razao"),
            "nome_fantasia": r.get("fantasia"),
            "contatos": contatos,
            "email": emails,
            "instagram": instas,
            "site": sites,
            "cidade": r.get("log_municipio"),
            "estado": r.get("log_uf"),
            "socios": [s.get("socios_nome") for s in socios if s.get("socios_nome")],
            "cnae_codigo": (r.get("cnae_principal") or "").split(" - ")[0] or None,
            "cnae_descricao": (r.get("cnae_principal") or "").split(" - ", 1)[-1] or None,
            # ---------- redes ----------
            "linkedin": _lista(enr.get("linkedin_principal"), enr.get("linkedin_texto")),
            "facebook": _lista(enr.get("facebook_principal"), enr.get("facebook_texto")),
            "google_maps": _lista(enr.get("google_maps_texto")),
            # ---------- empresa ----------
            "porte": config.PORTE_API.get(str(r.get("porte")), r.get("porte")),
            "situacao": config.SITUACAO.get(str(r.get("situacao_cadastral")),
                                            r.get("situacao_cadastral")),
            "data_situacao": _data(r.get("data_sit_cad")),
            "data_abertura": abertura,
            "idade_anos": (date.today().year - int(abertura[:4])) if abertura else None,
            "natureza_juridica": r.get("natureza_juridica"),
            "capital_social": r.get("capital_social"),
            "faturamento": r.get("faturamento"),
            "quadro_funcionarios": r.get("quadro_funcionarios"),
            "matriz_filial": {"1": "MATRIZ", "2": "FILIAL"}.get(str(r.get("matriz"))),
            "cnpj_base": (r.get("cnpj") or "")[:8] or None,
            # ---------- fiscal ----------
            "regime_tributario": (r.get("regime_tributario") or "").strip("; ") or None,
            "historico_regime_por_ano": [f"{d.get('ano')}={d.get('regime')}"
                                         for d in (r.get("historicoRegimePorAno") or [])
                                         if isinstance(d, dict)],
            "opcao_simples": r.get("opcao_simples"),
            "data_simples": _data(r.get("data_simples")),
            "data_exclusao_simples": _data(r.get("data_exc_simples")),
            "opcao_mei": r.get("opcao_mei"),
            "data_mei": _data(r.get("data_mei")),
            "data_exclusao_mei": _data(r.get("data_exc_mei")),
            # ---------- atividade ----------
            "cnae_secundario_codigos": _lista(r.get("cnae_secundario")),
            "cnae_secundario_descricoes": [],   # preenchido no join com a base
            # ---------- programas ----------
            "programas_especiais": _lista(prog),
            "importa_exporta": temp("IMPORTA"),
            "empresa_cidada": temp("CIDAD"),
            "pat": temp("PAT"),
            "recuperacao_judicial": temp("RECUPERACAO"),
            # ---------- endereço ----------
            "logradouro": " ".join(x for x in (r.get("log_tipo"), r.get("log_nome")) if x) or None,
            "numero": r.get("log_num"),
            "complemento": " ".join((r.get("log_comp") or "").split()) or None,
            "bairro": r.get("log_bairro"),
            "cep": r.get("log_cep"),
            "municipio_codigo": None,
            "pais": None,
            # ---------- sócios (mesma ordem da coluna socios) ----------
            "socios_qualificacoes": [s.get("socios_qualificacao") for s in socios],
            "socios_entrada": [_data(s.get("socios_entrada")) for s in socios],
            "socios_cpf": [s.get("socios_cpf_cnpj") for s in socios],
            "qtd_socios": len(socios),
            # ---------- dívida ativa detalhada ----------
            "qtd_dividas": len(dividas),
            "divida_valor_total": round(sum(
                float(d["dividas_valor"]) for d in dividas
                if str(d.get("dividas_valor", "")).replace(".", "").isdigit()), 2) or None,
            "dividas_valores": [d.get("dividas_valor") for d in dividas],
            "dividas_receitas": [d.get("dividas_receita") for d in dividas],
            "dividas_situacoes": [d.get("dividas_tipo_situacao") for d in dividas],
            "dividas_inscricoes": [d.get("dividas_inscricao") for d in dividas],
            "dividas_datas": [d.get("dividas_data") for d in dividas],
            "dividas_numeros": [d.get("dividas_numero") for d in dividas],
            "qtd_trimestres_com_divida": sum(
                1 for d in (r.get("historicoDividasPorTrimestre") or [])
                if isinstance(d, dict)
                and "NAO POSSUI" not in str(d.get("valor", "")).upper()),
            "historico_dividas": [f"{d.get('trimestreAno')}={d.get('valor')}"
                                  for d in (r.get("historicoDividasPorTrimestre") or [])
                                  if isinstance(d, dict)],
            # ---------- scraping: preenchido pelo apify ----------
            "maps_titulo": None, "maps_categoria": None, "maps_endereco": None,
            "instagram_bio": None, "instagram_seguidores": None,
            "instagram_categoria": None, "match_score": None,
            # ---------- procedência ----------
            "enrichment_vazio": not enr,
            "base_competencia": None, "extraido_em": None, "lote_id": None,
        }

        # Uma coluna só para filtrar risco no Excel, em vez de ler três.
        linha["situacao_alerta"] = bool(
            linha["situacao"] != "ATIVA" or linha["qtd_dividas"]
            or linha["recuperacao_judicial"])

        # Procedência: quem venceu a consolidação assina o campo. Recalculada
        # depois do Apify, em apify.enriquecer_lote.
        linha["fonte_contatos"] = _fontes(contatos, r, enr, "tel")
        linha["fonte_email"] = _fontes(emails, r, enr, "email")
        linha["fonte_instagram"] = ["empresaqui"] * len(instas)
        linha["fonte_site"] = _fontes(sites, r, enr, "site")
        linhas.append(linha)
    return linhas


# Um host de verdade: rótulo, ponto, e um sufixo de ao menos duas letras.
_HOST = re.compile(r"^[a-z0-9][a-z0-9._-]*\.[a-z]{2,}$", re.I)


def _url(v):
    """
    Devolve URL só quando há host de verdade.

    A versão anterior grudava o esquema em qualquer coisa: a base devolveu
    "www." para uma das empresas e saiu "https://www." na planilha —
    pior que vazio, porque parece link, o cliente clica e não vai a lugar
    nenhum. Apareceu na primeira entrega de verdade, com três empresas.
    """
    v = (str(v or "")).strip()
    if not v:
        return None
    sem_esquema = re.sub(r"^https?://", "", v, flags=re.I)
    host = re.split(r"[/?#]", sem_esquema, 1)[0]
    host = re.sub(r"^www\.", "", host, flags=re.I)
    if not _HOST.match(host):
        return None
    return v if v.lower().startswith(("http://", "https://")) else "https://" + v


def _fontes(valores, r, enr, tipo):
    """Marca a origem de cada valor, na mesma ordem da coluna."""
    cadastrais = {
        "tel": {_digitos(f"{r.get('ddd_1') or ''}{r.get('tel_1') or ''}"),
                _digitos(f"{r.get('ddd_2') or ''}{r.get('tel_2') or ''}")},
        "email": {(r.get("email") or "").lower()},
        "site": {_url(r.get("site"))},
    }[tipo]
    return ["receita" if v in cadastrais else "empresaqui" for v in valores]



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
        # Só resultado definitivo entra no cache. Falha de rede, 429 e 5xx são
        # transitórios: guardá-los marcaria o CNPJ como falho PARA SEMPRE, e a
        # empresa sumiria de toda lista futura sem o lote acusar erro nenhum.
        if http not in (200, 404):
            return
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
