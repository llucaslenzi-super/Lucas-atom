"""Leitura de planilha enviada (Porta B) e escrita do CSV final."""
from __future__ import annotations

import csv
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

def _celulas_xlsx(caminho: Path):
    """Lê .xlsx sem dependência externa: é um zip com XML dentro."""
    with zipfile.ZipFile(caminho) as z:
        compart = []
        if "xl/sharedStrings.xml" in z.namelist():
            txt = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            compart = [re.sub(r"<[^>]+>", "", s)
                       for s in re.findall(r"<si>(.*?)</si>", txt, re.S)]
        folhas = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet")]
        for folha in sorted(folhas):
            xml = z.read(folha).decode("utf-8", "replace")
            for linha in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
                valores = []
                for cel in re.findall(r"<c[^>]*?(?:\st=\"(\w+)\")?[^>]*>(.*?)</c>",
                                      linha, re.S):
                    tipo, conteudo = cel
                    v = re.search(r"<v>(.*?)</v>", conteudo, re.S)
                    if not v:
                        valores.append("")
                        continue
                    bruto = v.group(1)
                    if tipo == "s":
                        i = int(bruto)
                        valores.append(compart[i] if i < len(compart) else "")
                    else:
                        valores.append(bruto)
                yield valores
            break   # só a primeira planilha


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
