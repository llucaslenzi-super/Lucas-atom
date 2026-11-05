"""
Camada Apify — etapas 2 a 4 da spec original.

Roda DEPOIS do EmpresAqui, em 100% do lote (não só nos furos): a cobertura
do enrichment é parcial — medido em 2026-11-05, 4 de 11 CNPJs voltaram com
`enrichment: null` e os demais vieram com campos vazios.

  Maps      vortex_data/google-maps          tel, email, whatsapp, @IG, categoria
  Instagram apify/instagram-profile-scraper  bio, site, categoria — NO HANDLE
  LinkedIn  harvestapi/linkedin-company-employees   decisor

Instagram: SEMPRE pelo handle que o Maps extraiu. A busca por palavra-chave
(instagram-search-scraper) foi validada como lixo na spec original — "lenceria
paraguay" devolveu hospital no Azerbaijão.

Token: export APIFY_TOKEN=...
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.apify.com/v2"

ATOR_MAPS = "vortex_data~google-maps"
ATOR_INSTAGRAM = "apify~instagram-profile-scraper"
ATOR_LINKEDIN = "harvestapi~linkedin-company-employees"


class SemToken(RuntimeError):
    pass


def _token() -> str:
    t = (os.environ.get("APIFY_TOKEN") or "").strip()
    if not t:
        raise SemToken("Defina APIFY_TOKEN no ambiente.")
    return t


def _post(caminho: str, corpo: dict, timeout=900) -> list[dict]:
    """
    Roda um ator e devolve os itens do dataset.
    Usa run-sync-get-dataset-items: o Apify segura a conexão até terminar.
    """
    url = f"{API}/acts/{caminho}/run-sync-get-dataset-items?token={_token()}"
    req = urllib.request.Request(
        url,
        data=json.dumps(corpo).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            corpo_erro = e.read().decode("utf-8", "replace")[:300]
            if e.code in (401, 403):
                raise SemToken(f"HTTP {e.code}: {corpo_erro}")
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** tentativa * 5)
                continue
            raise RuntimeError(f"Apify HTTP {e.code}: {corpo_erro}")
        except Exception:
            time.sleep(2 ** tentativa * 5)
    return []


# ───────────────────────────────────────────────── Google Maps

def maps(termos: list[str], pais="Brazil", por_busca=10,
         teto_usd: float | None = 5.0) -> list[dict]:
    """
    termos: nomes/razões sociais. Mínimo de 10 places por busca é regra do ator.
    O add-on de contato só cobra onde encontra algo.
    """
    if not termos:
        return []
    corpo = {
        "searchStringsArray": termos,
        "locationQuery": pais,
        "maxCrawledPlacesPerSearch": max(10, int(por_busca)),   # mínimo 10
        "skipPlacesNotMatchingSearch": True,
        "extractContactsFromWebsite": True,
        "language": "pt-BR",
    }
    if teto_usd:
        corpo["maxTotalChargeUsd"] = teto_usd      # teto duro por run
    return _post(ATOR_MAPS, corpo)


def de_maps(item: dict) -> dict:
    emails = item.get("emails") or []
    whats = item.get("whatsapps") or []
    insta = item.get("instagrams") or []
    return {
        "maps_titulo": item.get("title"),
        "maps_telefone": item.get("phone"),
        "maps_site": item.get("website"),
        "maps_endereco": item.get("address"),
        "maps_categoria": item.get("categoryName"),
        "maps_email": emails[0] if emails else None,
        "maps_whatsapp": whats[0] if whats else None,
        "maps_instagram": insta[0] if insta else None,
        "maps_qtd_emails": len(emails),
    }


# ───────────────────────────────────────────────── Instagram

def _handle(url_ou_handle: str | None) -> str | None:
    if not url_ou_handle:
        return None
    s = str(url_ou_handle).strip().rstrip("/")
    if "instagram.com" in s:
        s = s.split("instagram.com/")[-1].split("/")[0].split("?")[0]
    return s.lstrip("@") or None


def instagram(handles: list[str]) -> list[dict]:
    """SEMPRE pelo handle. Nunca por palavra-chave."""
    limpos = [h for h in (_handle(x) for x in handles) if h]
    if not limpos:
        return []
    return _post(ATOR_INSTAGRAM, {"usernames": limpos})


def de_instagram(item: dict) -> dict:
    return {
        "ig_handle": item.get("username"),
        "ig_nome": item.get("fullName"),
        "ig_bio": item.get("biography"),
        "ig_site": item.get("externalUrl"),
        "ig_categoria": item.get("businessCategoryName"),
        "ig_seguidores": item.get("followersCount"),
    }


# ───────────────────────────────────────────────── LinkedIn

CARGOS_COMPRAS = [
    "Comprador", "Compras", "Suprimentos", "Procurement", "Supply Chain",
    "Gerente de Compras", "Diretor de Compras", "Head of Procurement",
]


def linkedin(empresas: list[str], cargos: list[str] | None = None,
             locais=("Brazil",), por_empresa=2, teto=50) -> list[dict]:
    if not empresas:
        return []
    return _post(ATOR_LINKEDIN, {
        "companies": empresas,
        "jobTitles": list(cargos or CARGOS_COMPRAS),
        "locations": list(locais),
        "profileScraperMode": "Full + email search ($12 per 1k)",
        "maxItems": teto,
        "maxItemsPerCompany": por_empresa,
        "companyBatchMode": "all_at_once",
    })


def de_linkedin(item: dict) -> dict:
    nome = " ".join(x for x in (item.get("firstName"), item.get("lastName")) if x)
    return {
        "li_decisor": nome or None,
        "li_cargo": item.get("headline"),
        "li_url": item.get("linkedinUrl"),
        "li_empresa_casada": item.get("companyName"),
        # Na spec original o e-mail veio vazio mesmo no modo "+email".
        # Não tratar como garantido.
        "li_email": item.get("email"),
    }


# ───────────────────────────────────────────────── casamento

def _norm(s) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    for ruido in (" LTDA", " S A", " S.A.", " SA", " EIRELI", " ME", " EPP", " -"):
        s = s.upper().replace(ruido, " ")
    return " ".join(s.split())


def casar(leads: list[dict], itens: list[dict], extrair, chave_item: str,
          chave_lead="razao_social", minimo=0.62) -> int:
    """
    Casa resultado de scraping de volta no lead certo, por similaridade de nome.

    Existe por causa do erro documentado na spec: "Lazos" casou com
    "Frigorífico Los Lazos". Abaixo do mínimo, não casa — prefere deixar
    vazio a casar errado.
    """
    from difflib import SequenceMatcher

    alvos = [(i, _norm(l.get(chave_lead))) for i, l in enumerate(leads)]
    casados = 0
    for item in itens:
        nome = _norm(item.get(chave_item))
        if not nome:
            continue
        melhor, pontos = None, 0.0
        for i, alvo in alvos:
            if not alvo:
                continue
            p = SequenceMatcher(None, nome, alvo).ratio()
            if p > pontos:
                melhor, pontos = i, p
        if melhor is not None and pontos >= minimo:
            leads[melhor].update(extrair(item))
            leads[melhor]["match_score"] = round(pontos, 3)
            casados += 1
    return casados


def enriquecer_lote(leads: list[dict], usar_maps=True, usar_ig=True,
                    usar_li=False, pais="Brazil", teto_usd=5.0) -> dict:
    """
    Roda a camada Apify sobre um lote de leads já enriquecidos pelo EmpresAqui.
    Altera `leads` no lugar. Devolve o resumo do que casou.
    """
    resumo = {}
    nomes = [l.get("razao_social") for l in leads if l.get("razao_social")]

    if usar_maps and nomes:
        itens = maps(nomes, pais=pais, teto_usd=teto_usd)
        resumo["maps_itens"] = len(itens)
        resumo["maps_casados"] = casar(leads, itens, de_maps, "title")

    if usar_ig:
        # handle do EmpresAqui OU do Maps — nunca busca por palavra-chave
        handles = [h for h in (_handle(l.get("enr_instagram_principal")
                                       or l.get("maps_instagram")) for l in leads) if h]
        if handles:
            itens = instagram(handles)
            resumo["ig_itens"] = len(itens)
            mapa = {(_handle(i.get("username")) or "").lower(): i for i in itens}
            n = 0
            for l in leads:
                h = (_handle(l.get("enr_instagram_principal")
                             or l.get("maps_instagram")) or "").lower()
                if h and h in mapa:
                    l.update(de_instagram(mapa[h]))
                    n += 1
            resumo["ig_casados"] = n

    if usar_li and nomes:
        itens = linkedin(nomes)
        resumo["li_itens"] = len(itens)
        resumo["li_casados"] = casar(leads, itens, de_linkedin, "companyName")

    return resumo
