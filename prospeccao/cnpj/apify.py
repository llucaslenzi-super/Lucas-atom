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

# IDs confirmados nas rodadas de exploração. São públicos: qualquer conta
# usa os mesmos, com o próprio token.
ATOR_MAPS = "vortex_data~google-maps"               # AabCualFIriz3X6Fs
ATOR_INSTAGRAM = "apify~instagram-profile-scraper"  # dSCLg0C3YEZ83HzYX
ATOR_LINKEDIN = "harvestapi~linkedin-company-employees"   # Vb6LZkh4EqRlR0Ka9

# Opcional: enriquece um perfil de LinkedIn que você JÁ tem a URL.
ATOR_LINKEDIN_PERFIL = "harvestapi~linkedin-profile-scraper"   # LpVuK3Zozwuipa5bp

# NÃO USAR: apify/instagram-search-scraper (DrF9mzPPEuVizVF4l).
# Busca por palavra-chave, validada como lixo — "lenceria paraguay" devolveu
# hospital no Azerbaijão e cinema na Índia. Instagram é sempre pelo handle.


class SemToken(RuntimeError):
    pass


def _token() -> str:
    t = (os.environ.get("APIFY_TOKEN") or "").strip()
    if not t:
        raise SemToken("Defina APIFY_TOKEN no ambiente.")
    return t


def _post(caminho: str, corpo: dict, timeout=900,
          teto_usd: float | None = None) -> list[dict]:
    """
    Roda um ator e devolve os itens do dataset.
    Usa run-sync-get-dataset-items: o Apify segura a conexão até terminar.

    O teto vai como PARÂMETRO DE EXECUÇÃO, não dentro do corpo. Dentro do
    corpo só funciona se aquele ator específico souber ler o campo — e era
    exatamente o que acontecia: o Maps tinha teto e o Instagram e o LinkedIn
    rodavam soltos, porque ninguém passou o campo para eles. Aqui o teto vale
    para os três, e para qualquer ator que entre depois.
    """
    params = {"token": _token()}
    if teto_usd:
        params["maxTotalChargeUsd"] = f"{float(teto_usd):.4f}"
    url = (f"{API}/acts/{caminho}/run-sync-get-dataset-items?"
           + urllib.parse.urlencode(params))
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


def custo_do_ultimo_run(caminho: str) -> float | None:
    """
    Quanto o último run deste ator custou, em dólar.

    `run-sync-get-dataset-items` devolve só os itens do dataset: não há como
    saber o custo pela resposta. Então perguntamos pelo último run do ator.

    Pressuposto, explícito: o worker é único (flock em worker.lock), então o
    último run deste ator com este token é o nosso. Se um dia houver dois
    workers, isto passa a ser aproximação e precisa do runId de verdade.

    Devolve None quando não consegue ler — e None não é zero. Gravar zero
    seria afirmar que foi de graça.
    """
    url = (f"{API}/acts/{caminho}/runs?"
           + urllib.parse.urlencode({"token": _token(), "limit": 1, "desc": "true"}))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            itens = json.loads(r.read().decode()).get("data", {}).get("items", [])
        if not itens:
            return None
        v = itens[0].get("usageTotalUsd")
        return float(v) if v is not None else None
    except Exception:
        return None


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
        # O Maps também lê o campo no corpo; manter os dois não custa nada.
        corpo["maxTotalChargeUsd"] = teto_usd
    return _post(ATOR_MAPS, corpo, teto_usd=teto_usd)


def de_maps(item: dict) -> dict:
    """
    TODAS as listas, não o primeiro item.

    O código anterior guardava emails[0] e descartava o resto — um lugar com
    quatro e-mails entregava um. O que o Maps acha entra nas MESMAS colunas
    do EmpresAqui, não em colunas maps_* paralelas.
    """
    return {
        "maps_titulo": item.get("title"),
        "maps_endereco": item.get("address"),
        "maps_categoria": item.get("categoryName"),
        # para fundir nas colunas consolidadas:
        "_contatos": [item.get("phone")] + list(item.get("whatsapps") or []),
        "_email": list(item.get("emails") or []),
        "_instagram": list(item.get("instagrams") or []),
        "_site": [item.get("website")],
    }


# ───────────────────────────────────────────────── Instagram

def _handle(url_ou_handle: str | None) -> str | None:
    if not url_ou_handle:
        return None
    s = str(url_ou_handle).strip().rstrip("/")
    if "instagram.com" in s:
        s = s.split("instagram.com/")[-1].split("/")[0].split("?")[0]
    return s.lstrip("@") or None


def instagram(handles: list[str], teto_usd: float | None = None) -> list[dict]:
    """SEMPRE pelo handle. Nunca por palavra-chave."""
    limpos = [h for h in (_handle(x) for x in handles) if h]
    if not limpos:
        return []
    return _post(ATOR_INSTAGRAM, {"usernames": limpos}, teto_usd=teto_usd)


def de_instagram(item: dict) -> dict:
    return {
        "instagram_bio": item.get("biography"),
        "instagram_categoria": item.get("businessCategoryName"),
        "instagram_seguidores": item.get("followersCount"),
        "_site": [item.get("externalUrl")],
        "_instagram": [item.get("username")],
    }


# ───────────────────────────────────────────────── LinkedIn

CARGOS_COMPRAS = [
    "Comprador", "Compras", "Suprimentos", "Procurement", "Supply Chain",
    "Gerente de Compras", "Diretor de Compras", "Head of Procurement",
]


def linkedin(empresas: list[str], cargos: list[str] | None = None,
             locais=("Brazil",), por_empresa=2, teto=50,
             teto_usd: float | None = None) -> list[dict]:
    if not empresas:
        return []
    return _post(ATOR_LINKEDIN, teto_usd=teto_usd, corpo={
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
          chave_lead="razao_social", minimo=0.62, fonte="maps") -> int:
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
            _fundir(leads[melhor], extrair(item), fonte)
            leads[melhor]["match_score"] = round(pontos, 3)
            casados += 1
    return casados


def _fundir(lead: dict, novo: dict, fonte: str):
    """
    Campo _xxx entra na coluna consolidada xxx, desduplicado, e marca a
    procedência na posição correspondente. O resto vira coluna própria.
    """
    from .empresaqui import _digitos, _emails_validos, _handle_ig, _url
    limpar = {"_contatos": lambda v: _digitos(v) or None,
              "_email": lambda v: str(v).strip().lower(),
              "_instagram": _handle_ig,
              "_site": _url}
    for k, v in novo.items():
        if not k.startswith("_"):
            if v not in (None, ""):
                lead[k] = v
            continue
        col = k[1:]
        atual = lead.get(col) or []
        fontes = lead.get(f"fonte_{col}") or []
        for bruto in (v or []):
            limpo = limpar[k](bruto)
            if not limpo or limpo in atual:
                continue
            if col == "email" and not _emails_validos([limpo]):
                continue
            atual.append(limpo)
            fontes.append(fonte)
        lead[col] = atual
        lead[f"fonte_{col}"] = fontes


def enriquecer_lote(leads: list[dict], usar_maps=True, usar_ig=True,
                    usar_li=False, pais="Brazil", teto_usd=5.0) -> dict:
    """
    Roda a camada Apify sobre um lote de leads já enriquecidos pelo EmpresAqui.
    Altera `leads` no lugar. Devolve o resumo do que casou e o CUSTO REAL.

    O teto é do LOTE, não de cada ator. Cada ator recebe o que sobrou do teto,
    e quando não sobra nada o ator é pulado e isso fica registrado. Antes o
    teto ia só para o Maps, e Instagram e LinkedIn rodavam sem limite nenhum —
    o LinkedIn com "Full + email search", que é o mais caro dos três.

    `custo_usd` pode vir None: o Apify não devolve custo na mesma chamada, e
    se a leitura falhar, None é a resposta honesta. Zero seria afirmar que
    foi de graça.
    """
    resumo = {"custo_usd": 0.0, "pulados": []}
    nomes = [l.get("razao_social") for l in leads if l.get("razao_social")]
    gasto_desconhecido = False

    def restante():
        return None if teto_usd is None else max(0.0, teto_usd - resumo["custo_usd"])

    def cobrar(ator: str):
        nonlocal gasto_desconhecido
        c = custo_do_ultimo_run(ator)
        if c is None:
            gasto_desconhecido = True
        else:
            resumo["custo_usd"] = round(resumo["custo_usd"] + c, 4)

    def tem_verba(ator: str) -> bool:
        r = restante()
        if r is not None and r <= 0:
            resumo["pulados"].append(ator)
            return False
        return True

    if usar_maps and nomes and tem_verba("maps"):
        itens = maps(nomes, pais=pais, teto_usd=restante())
        cobrar(ATOR_MAPS)
        resumo["maps_itens"] = len(itens)
        resumo["maps_casados"] = casar(leads, itens, de_maps, "title")

    if usar_ig:
        # handle do EmpresAqui OU do Maps — nunca busca por palavra-chave
        handles = [h for l in leads for h in (l.get("instagram") or [])]
        if handles and tem_verba("instagram"):
            itens = instagram(handles, teto_usd=restante())
            cobrar(ATOR_INSTAGRAM)
            resumo["ig_itens"] = len(itens)
            mapa = {(_handle(i.get("username")) or "").lower(): i for i in itens}
            n = 0
            for l in leads:
                for h in (l.get("instagram") or []):
                    chave = (_handle(h) or "").lower()
                    if chave in mapa:
                        _fundir(l, de_instagram(mapa[chave]), "instagram")
                        n += 1
                        break
            resumo["ig_casados"] = n

    if usar_li and nomes and tem_verba("linkedin"):
        itens = linkedin(nomes, teto_usd=restante())
        cobrar(ATOR_LINKEDIN)
        resumo["li_itens"] = len(itens)
        resumo["li_casados"] = casar(leads, itens, de_linkedin, "companyName")

    if gasto_desconhecido:
        # Parte do custo não pôde ser lida: o número deixa de ser confiável e
        # é melhor dizer que não se sabe.
        resumo["custo_usd"] = None
    return resumo
