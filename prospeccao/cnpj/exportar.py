"""Leitura de planilha enviada (Porta B) e escrita do CSV final."""
from __future__ import annotations

import csv
import html
import io
import re
import zipfile
from pathlib import Path

from .empresaqui import normalizar, so_digitos

# Ordem das colunas no CSV final: CNPJ primeiro, razão social depois.
COLUNAS_SAIDA = [
    "cnpj", "razao_social", "nome_fantasia", "situacao", "matriz_filial",
    "uf", "municipio", "bairro", "logradouro", "cep",
    "cnae_principal", "cnae_descricao", "cnae_secundario",
    "natureza_juridica", "porte", "capital_social", "faturamento",
    "quadro_funcionarios", "regime_tributario", "opcao_simples", "opcao_mei",
    "data_abertura", "programas_especiais", "importa_exporta",
    # contato
    "telefone_1", "telefone_2", "email", "site",
    # enriquecido
    "enr_whatsapp_principal", "enr_telefone_principal", "enr_email_principal",
    "enr_instagram_principal", "enr_linkedin_principal", "enr_facebook_principal",
    "enr_site_validado", "enr_score_site_match", "enr_fonte_atualizada_em",
    # decisor
    "socio_admin", "socio_admin_qualificacao", "qtd_socios",
    # risco
    "qtd_dividas",
    # procedência — auditoria e LGPD
    "fonte_telefone", "fonte_email", "fonte_whatsapp",
]


# ─────────────────────────────────────────── entrada

def _coluna(ref: str) -> int:
    """Referência de célula para índice: 'A1' -> 0, 'C5' -> 2, 'AA2' -> 26."""
    n = 0
    for c in ref:
        if not c.isalpha():
            break
        n = n * 26 + (ord(c.upper()) - 64)
    return n - 1


def _texto(xml: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _celulas_xlsx(caminho: Path):
    """
    Lê .xlsx sem dependência externa: é um zip com XML dentro.

    Dois detalhes que o formato impõe e que não dá pra ignorar:
      - texto não fica na célula. A célula marca t="s" e guarda o ÍNDICE
        de xl/sharedStrings.xml. Sem ler o t, o CNPJ vira "0", "1", "2".
      - célula vazia pode vir auto-fechada (<c r="C5"/>) ou simplesmente
        faltar. Por isso posicionamos pelo r="C5", e não pela ordem.
    """
    with zipfile.ZipFile(caminho) as z:
        compart = []
        if "xl/sharedStrings.xml" in z.namelist():
            txt = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            compart = [_texto(s) for s in re.findall(r"<si>(.*?)</si>", txt, re.S)]

        folhas = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
        if not folhas:
            return
        xml = z.read(folhas[0]).decode("utf-8", "replace")   # só a primeira planilha

        for linha in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
            valores = []
            for m in re.finditer(r"<c\b([^>]*?)(?:/>|>(.*?)</c>)", linha, re.S):
                attrs, conteudo = m.group(1), m.group(2) or ""
                ref = re.search(r'\br="([A-Z]+\d+)"', attrs)
                i = _coluna(ref.group(1)) if ref else len(valores)
                while len(valores) <= i:
                    valores.append("")

                tipo = re.search(r'\bt="([^"]+)"', attrs)
                tipo = tipo.group(1) if tipo else "n"

                if tipo == "inlineStr":
                    valores[i] = _texto(conteudo)
                    continue
                v = re.search(r"<v>(.*?)</v>", conteudo, re.S)
                if not v:
                    continue
                if tipo == "s":
                    k = int(v.group(1))
                    valores[i] = compart[k] if k < len(compart) else ""
                else:
                    valores[i] = html.unescape(v.group(1))
            yield valores


def _celulas_csv(caminho: Path):
    with open(caminho, newline="", encoding="utf-8-sig", errors="replace") as f:
        amostra = f.read(8192)
        f.seek(0)
        try:
            d = csv.Sniffer().sniff(amostra, delimiters=",;\t|")
        except csv.Error:
            d = csv.excel
            d.delimiter = ";" if amostra.count(";") > amostra.count(",") else ","
        yield from csv.reader(f, d)


def ler_cnpjs(caminho) -> tuple[list[str], dict]:
    """
    Extrai CNPJs de uma planilha SEM pedir mapeamento de coluna:
    escolhe a coluna em que mais valores viram CNPJ válido.
    """
    caminho = Path(caminho)
    linhas = list(_celulas_xlsx(caminho) if caminho.suffix.lower() in (".xlsx", ".xlsm")
                  else _celulas_csv(caminho))
    if not linhas:
        return [], {"linhas": 0}

    largura = max(len(l) for l in linhas)
    pontos = [0] * largura
    for linha in linhas:
        for i, v in enumerate(linha):
            if normalizar(v):
                pontos[i] += 1
    coluna = max(range(largura), key=lambda i: pontos[i]) if largura else 0

    vistos, cnpjs, invalidos = set(), [], 0
    for linha in linhas:
        if coluna >= len(linha):
            continue
        bruto = linha[coluna]
        if not so_digitos(bruto):
            continue
        n = normalizar(bruto)
        if not n:
            invalidos += 1
            continue
        if n[0] not in vistos:
            vistos.add(n[0])
            cnpjs.append(n[0])

    return cnpjs, {
        "linhas": len(linhas),
        "coluna_detectada": coluna,
        "validos": len(cnpjs),
        "invalidos_descartados": invalidos,
    }


# ─────────────────────────────────────────── saída

def escrever_csv(linhas: list[dict], caminho, colunas=None) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not linhas:
        caminho.write_text("", encoding="utf-8-sig")
        return caminho

    if colunas is None:
        presentes = [c for c in COLUNAS_SAIDA if any(c in l for l in linhas)]
        extras = sorted({k for l in linhas for k in l} - set(presentes))
        colunas = presentes + extras

    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for l in linhas:
            # Campo sem dado sai VAZIO. Nunca inventado.
            w.writerow({c: ("" if l.get(c) is None else l.get(c)) for c in colunas})
    return caminho
