"""Leitura de planilha enviada (Porta B) e escrita do CSV final."""
from __future__ import annotations

import csv
import html
import io
import re
import zipfile
from pathlib import Path

from . import colunas as _c
from .empresaqui import normalizar, so_digitos

# A ordem de saída vive em colunas.py, e em lugar nenhum mais.
#
# Havia aqui uma segunda lista, COLUNAS_SAIDA, de duas versões atrás. Ela
# pedia uf, municipio, cnae_principal, telefone_1, enr_* e socio_admin —
# nomes que achatar() parou de produzir quando as colunas foram reorganizadas
# em blocos. O resultado era silencioso: nenhuma dessas colunas casava, tudo
# caía no caminho de "extras" ordenado por alfabeto, e a ordem que o cliente
# ditou (cnpj, razao_social, nome_fantasia, contatos, email, instagram, site,
# cidade, estado, socios, cnae_codigo, cnae_descricao) NÃO era a que saía.
#
# Duas listas de ordem é uma a mais. Esta é a que fica.


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
        oficiais = _c.colunas_de(None)
        presentes = [c for c in oficiais if any(c in l for l in linhas)]
        extras = sorted({k for l in linhas for k in l} - set(presentes))
        colunas = presentes + extras

    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for l in linhas:
            # Campo sem dado sai VAZIO. Nunca inventado.
            w.writerow({c: ("" if l.get(c) is None else l.get(c)) for c in colunas})
    return caminho


# ════════════════════════════════════════════════════════════════════
#  ESCRITA NOS TRÊS FORMATOS
#  O separador é decidido AQUI, não na consolidação: a mesma lista vira
#  ";" no CSV e XLSX e " - " no PDF.
# ════════════════════════════════════════════════════════════════════

def _preparar(linhas, blocos=None, formato="csv"):
    """Escolhe colunas, remove as vazias de verdade e junta os multivalores."""
    cols = _c.colunas_de(blocos)

    # Vazia é vazia de VALOR, não de chave. O código antigo testava
    # `c in linha`, e como achatar() cria toda chave, nada era removido.
    def tem_valor(c):
        return any(l.get(c) not in (None, "", [], {}, False) or
                   (isinstance(l.get(c), (int, float)) and l.get(c) == 0)
                   for l in linhas)

    cols = [c for c in cols if tem_valor(c)]
    saida = [{c: _c.juntar(l.get(c), formato) for c in cols} for l in linhas]
    return cols, saida


def escrever_xlsx(linhas, caminho, blocos=None):
    """Cabeçalho congelado, autofiltro, largura automática, CNPJ como TEXTO."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    cols, dados = _preparar(linhas, blocos, "xlsx")
    caminho = Path(caminho); caminho.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook(); ws = wb.active; ws.title = "Leads"

    ws.append([_c.rotulo(c) for c in cols])
    for cel in ws[1]:
        cel.font = Font(bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor="1F3864")
        cel.alignment = Alignment(vertical="center")

    for linha in dados:
        ws.append([linha[c] for c in cols])

    # CNPJ e CEP como texto, senão o Excel come o zero da frente
    for i, c in enumerate(cols, 1):
        letra = get_column_letter(i)
        if c in _c.TEXTO_FORCADO:
            for cel in ws[letra][1:]:
                cel.number_format = "@"
        largura = max([len(_c.rotulo(c))] + [len(str(l[c])) for l in dados[:200]] or [10])
        ws.column_dimensions[letra].width = min(max(largura + 2, 10), 55)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(caminho)
    return caminho


# Blocos do dossiê, na ordem em que aparecem na página
_DOSSIE = [
    ("CONTATO", ["contatos", "email", "instagram", "site", "linkedin", "facebook"]),
    ("SÓCIOS", ["socios", "socios_qualificacoes", "qtd_socios"]),
    ("QUALIFICAÇÃO", ["cnae_codigo", "cnae_descricao", "porte", "situacao",
                      "data_abertura", "capital_social", "faturamento",
                      "quadro_funcionarios", "importa_exporta"]),
    ("ENDEREÇO", ["logradouro", "numero", "complemento", "bairro", "cidade",
                  "estado", "cep"]),
    ("RISCO", ["qtd_dividas", "divida_valor_total", "dividas_receitas",
               "dividas_situacoes", "recuperacao_judicial"]),
]


def escrever_pdf(linhas, caminho, blocos=None):
    """Dossiê: uma página por empresa. O bloco RISCO só sai se houver alerta."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                    SimpleDocTemplate, Spacer, Table, TableStyle)

    caminho = Path(caminho); caminho.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(caminho), pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=16*mm, bottomMargin=16*mm,
                            title="Dossiê de Prospecção")
    tit = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=15, leading=18,
                         textColor=colors.HexColor("#1F3864"))
    sub = ParagraphStyle("s", fontName="Helvetica", fontSize=9, leading=12,
                         textColor=colors.HexColor("#666666"))
    sec = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=8, leading=14,
                         textColor=colors.HexColor("#1F3864"), spaceBefore=7)
    pe = ParagraphStyle("f", fontName="Helvetica", fontSize=7, leading=9,
                        textColor=colors.HexColor("#888888"))
    corpo = ParagraphStyle("c", fontName="Helvetica", fontSize=8.5, leading=11)

    pedidos = set(_c.colunas_de(blocos))

    # O dossiê é documento de leitura. Itaú Unibanco tem 64 sócios: listar
    # todos estoura a página, empurra o rodapé sozinho para a página seguinte
    # e ninguém lê mesmo. A lista inteira continua no CSV e no XLSX.
    TETO = 8

    def _curto(valor):
        if not isinstance(valor, (list, tuple)):
            return _c.juntar(valor, "pdf")
        itens = [str(x).strip() for x in valor if x not in (None, "", [])]
        itens = list(dict.fromkeys(itens))
        if len(itens) <= TETO:
            return " - ".join(itens)
        return " - ".join(itens[:TETO]) + f"  (+{len(itens) - TETO} não listados)"

    hist = []
    for n, l in enumerate(linhas):
        v = _curto if False else (lambda c: _curto(l.get(c)))
        hist += [Paragraph(l.get("razao_social") or "—", tit),
                 Paragraph(f"{v('nome_fantasia') or '—'} · CNPJ {v('cnpj')} · "
                           f"{v('cidade')}/{v('estado')}", sub), Spacer(1, 5)]

        for nome, campos in _DOSSIE:
            if nome == "RISCO" and not l.get("situacao_alerta"):
                continue
            dados = [[_c.rotulo(c), Paragraph(v(c), corpo)]
                     for c in campos if c in pedidos and v(c)]
            if not dados:
                continue
            hist.append(Paragraph(nome, sec))
            t = Table(dados, colWidths=[42*mm, 132*mm])
            t.setStyle(TableStyle([
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#E5E5E5")),
            ]))
            hist.append(t)

        # KeepTogether impede o rodapé de cair sozinho numa página órfã
        hist.append(KeepTogether([
            Spacer(1, 7),
            Paragraph(f"Origem dos contatos: {v('fonte_contatos') or '—'} · "
                      f"Base {v('base_competencia') or '—'} · "
                      f"Extraído em {v('extraido_em') or '—'}", pe)]))
        if n < len(linhas) - 1:
            hist.append(PageBreak())
    doc.build(hist)
    return caminho


def escrever(linhas, destino, formatos=("csv",), blocos=None):
    """Gera os formatos pedidos a partir do mesmo lote. Devolve {formato: caminho}."""
    destino = Path(destino)
    feitos = {}
    for f in formatos:
        alvo = destino.with_suffix("." + f)
        if f == "csv":
            cols, dados = _preparar(linhas, blocos, "csv")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with open(alvo, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, delimiter=";",
                                   extrasaction="ignore", quoting=csv.QUOTE_ALL)
                fh.write(";".join(f'"{_c.rotulo(c)}"' for c in cols) + "\r\n")
                w.writerows(dados)
        elif f == "xlsx":
            escrever_xlsx(linhas, alvo, blocos)
        elif f == "pdf":
            escrever_pdf(linhas, alvo, blocos)
        else:
            raise ValueError(f"formato desconhecido: {f}")
        feitos[f] = alvo
    return feitos
