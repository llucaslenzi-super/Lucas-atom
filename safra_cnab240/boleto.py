"""
Gerador de boleto PDF Cobrança Registrada Safra.

Baseado no manual CNAB 240 Safra (agosto/2026), seções:
  8.1.2 Formatação código de barras + linha digitável
  8.1.4 Cálculo DV linha digitável (módulo 10, pesos 2-1)
  8.1.5 Cálculo DAC código de barras (módulo 11, pesos 2-9)
  8.2   Fator de vencimento (base 29/05/2022)
"""

from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode.common import I2of5
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing

import config as CFG


# ---------- Cálculos ----------

DATA_BASE_FATOR = date(2022, 5, 29)


def fator_vencimento(data_venc):
    """Dias entre a data base 29/05/2022 e a data de vencimento."""
    delta = (data_venc - DATA_BASE_FATOR).days
    # Ciclo: fator vai de 1000 (22/02/2025 = dia 999+1) a 9999.
    # Depois retorna a 1000. Aqui simplesmente retornamos o delta - só é válido
    # a partir do dia em que delta >= 1000. Manual confirma tabela: 22/02/2025 = 1000.
    if delta < 1000:
        raise ValueError(
            f"Vencimento {data_venc} anterior a 22/02/2025 - fator invalido no layout novo"
        )
    if delta > 9999:
        # Ciclo se repete: 14/10/2049 volta pra 1000
        delta = ((delta - 1000) % 9000) + 1000
    return delta


def dac_codigo_barras(barras_43):
    """DAC módulo 11 - pesos 2-9 direita para esquerda, para as 43 posições
    (posições 1-4 e 6-44 do código de barras, pulando a posição 5)."""
    assert len(barras_43) == 43
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for i, ch in enumerate(reversed(barras_43)):
        p = pesos[i % 8]
        soma += int(ch) * p
    resto = soma % 11
    # Manual pág 48: "Se na divisão o resto for 0 (zero), 10 (dez) ou 1 (um)
    # o DAC será sempre 1 (um)".
    if resto in (0, 1, 10):
        return "1"
    return str(11 - resto)


def dv_modulo10(campo):
    """DV módulo 10 dos campos da linha digitável.
    Pesos 2-1 alternando da direita para esquerda. Soma dos DÍGITOS do produto
    (14 vira 1+4). DV = 10 - resto. Se resto = 0, DV = 0."""
    soma = 0
    peso = 2
    for ch in reversed(campo):
        produto = int(ch) * peso
        soma += produto // 10 + produto % 10
        peso = 1 if peso == 2 else 2
    resto = soma % 10
    return "0" if resto == 0 else str(10 - resto)


def codigo_barras_44(nosso_numero, data_venc, valor_centavos):
    """Monta os 44 dígitos do código de barras conforme layout Safra."""
    fator = fator_vencimento(data_venc)
    # Campo livre (24 chars): Sistema(1) + Ag(5) + ContaCompleta(9) + N/N(9) + Tipo(1)
    #                          = 7 + 02900 + 005875216 + 000000001 + 2
    campo_livre = (
        CFG.SISTEMA_SAFRA          # 1 (pos 20)
        + CFG.AGENCIA              # 5 (pos 21-25)
        + CFG.CONTA_COMPLETA       # 9 (pos 26-34) - conta com dígito
        + nosso_numero.rjust(9, "0")   # 9 (pos 35-43)
        + "2"                       # 1 (pos 44) - Tipo Cobrança Registrada
    )
    assert len(campo_livre) == 25, f"campo_livre={len(campo_livre)}"
    valor_str = str(valor_centavos).rjust(10, "0")
    barras_sem_dac = (
        CFG.BANCO                              # 1-3
        + "9"                                  # 4 - Moeda Real
        + str(fator).rjust(4, "0")             # 6-9 - Fator
        + valor_str                            # 10-19
        + campo_livre                          # 20-43
    )
    assert len(barras_sem_dac) == 43
    dac = dac_codigo_barras(barras_sem_dac)
    return barras_sem_dac[:4] + dac + barras_sem_dac[4:]


def linha_digitavel(cod_barras):
    """Monta a linha digitável formatada a partir do código de barras (44 dígitos).

    Layout Safra (pág 45 do manual):
      Campo 1: BANCO(3)+MOEDA(1)+SISTEMA(1)+AG_4primeiros(4) + DV1
      Campo 2: AG_ultimoDigito(1)+CONTA(9) + DV2
      Campo 3: NOSSO_NUMERO(9)+TIPO_COBRANCA(1) + DV3
      Campo 4: DAC (1)
      Campo 5: FATOR_VENC(4)+VALOR(10)

    Retorna string formatada:
      99999.99999 99999.999999 99999.999999 9 99999999999999
    """
    assert len(cod_barras) == 44
    # Extração dos pedaços (index 0-based)
    banco = cod_barras[0:3]        # 3
    moeda = cod_barras[3]          # 1
    dac = cod_barras[4]            # 1
    fator = cod_barras[5:9]        # 4
    valor = cod_barras[9:19]       # 10
    campo_livre = cod_barras[19:44]  # 25 (pos 20-44 do BR)

    sistema = campo_livre[0]              # 1 (pos 20)
    agencia = campo_livre[1:6]            # 5 (pos 21-25)
    conta = campo_livre[6:15]             # 9 (pos 26-34)
    nosso_num = campo_livre[15:24]        # 9 (pos 35-43)
    tipo_cob = campo_livre[24]            # 1 (pos 44)

    # Campo 1: BANCO+MOEDA+SISTEMA+AG_4primeiros = 9 dígitos + DV
    c1 = banco + moeda + sistema + agencia[:4]
    c1_dv = dv_modulo10(c1)

    # Campo 2: AG_ultimoDigito + CONTA = 10 dígitos + DV
    c2 = agencia[4] + conta
    c2_dv = dv_modulo10(c2)

    # Campo 3: NOSSO_NUMERO + TIPO_COBRANCA = 10 dígitos + DV
    c3 = nosso_num + tipo_cob
    c3_dv = dv_modulo10(c3)

    # Campo 5: FATOR + VALOR = 14 dígitos
    c5 = fator + valor

    # Formatação: XXXXX.XXXXX XXXXX.XXXXXX XXXXX.XXXXXX X XXXXXXXXXXXXXX
    return (
        f"{c1[:5]}.{c1[5:]}{c1_dv} "
        f"{c2[:5]}.{c2[5:]}{c2_dv} "
        f"{c3[:5]}.{c3[5:]}{c3_dv} "
        f"{dac} "
        f"{c5}"
    )


# ---------- Layout PDF ----------

def _fmt_valor(centavos):
    v = centavos / 100.0
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_data(d):
    return d.strftime("%d/%m/%Y")


def gerar_boleto_pdf(titulo, caminho_pdf):
    """Gera 1 PDF de boleto no caminho especificado."""
    cod_barras = codigo_barras_44(
        titulo["nosso_numero"],
        titulo["data_vencimento"],
        titulo["valor_centavos"],
    )
    ld = linha_digitavel(cod_barras)

    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    largura, altura = A4

    # Margem
    m = 15 * mm
    y = altura - m

    # ---------- Recibo do Pagador ----------
    def cabecalho(y0, titulo_secao):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(m, y0, titulo_secao)
        return y0 - 6 * mm

    def caixa(x, y0, w, h):
        c.rect(x, y0 - h, w, h)

    def rotulo(x, y0, texto):
        c.setFont("Helvetica", 6)
        c.drawString(x + 1 * mm, y0 - 3 * mm, texto)

    def valor(x, y0, texto, size=9, bold=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x + 1 * mm, y0 - 8 * mm, str(texto))

    def linha_horiz(y0):
        c.setStrokeGray(0.3)
        c.line(m, y0, largura - m, y0)

    # RECIBO DO PAGADOR
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m, y, "RECIBO DO PAGADOR")
    y -= 6 * mm

    # Linha 1: Banco 422-7
    c.setFont("Helvetica-Bold", 14)
    c.drawString(m, y - 5 * mm, "BANCO SAFRA S/A")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(m + 60 * mm, y - 5 * mm, f"| {CFG.BANCO}-{CFG.BANCO_DV}")
    c.setFont("Helvetica", 9)
    c.drawRightString(largura - m, y - 5 * mm, ld)
    y -= 10 * mm

    # Beneficiário + Ag/Cod Beneficiário
    caixa(m, y, largura - 2 * m, 10 * mm)
    rotulo(m, y, "Beneficiario")
    valor(m, y, f"{CFG.RAZAO_SOCIAL} - CNPJ: {CFG.CNPJ[:2]}.{CFG.CNPJ[2:5]}.{CFG.CNPJ[5:8]}/{CFG.CNPJ[8:12]}-{CFG.CNPJ[12:]}")
    caixa(m + 120 * mm, y, largura - 2 * m - 120 * mm, 10 * mm)
    rotulo(m + 120 * mm, y, "Agencia / Codigo Beneficiario")
    valor(m + 120 * mm, y, f"{CFG.AGENCIA} / {CFG.CONTA_COMPLETA}")
    y -= 10 * mm

    # Nosso Número + Nº Documento + Espécie + Aceite + Data processamento
    w = (largura - 2 * m) / 5
    labels = [
        ("Nosso Numero", titulo["nosso_numero"]),
        ("Nº do Documento", titulo["seu_numero"]),
        ("Especie", "DM"),
        ("Aceite", "N"),
        ("Data Processamento", _fmt_data(date.today())),
    ]
    for i, (lab, val) in enumerate(labels):
        caixa(m + i * w, y, w, 10 * mm)
        rotulo(m + i * w, y, lab)
        valor(m + i * w, y, val)
    y -= 10 * mm

    # Vencimento + Valor Documento
    caixa(m, y, largura - 2 * m - 60 * mm, 10 * mm)
    rotulo(m, y, "Vencimento")
    valor(m, y, _fmt_data(titulo["data_vencimento"]))
    caixa(m + (largura - 2 * m - 60 * mm), y, 60 * mm, 10 * mm)
    rotulo(m + (largura - 2 * m - 60 * mm), y, "(=) Valor do Documento")
    valor(m + (largura - 2 * m - 60 * mm), y, _fmt_valor(titulo["valor_centavos"]), bold=True)
    y -= 10 * mm

    # Pagador
    p = titulo["pagador"]
    caixa(m, y, largura - 2 * m, 14 * mm)
    rotulo(m, y, "Pagador")
    doc_fmt = _fmt_doc(p["cpf_cnpj"], p["tipo_inscricao"])
    c.setFont("Helvetica", 9)
    c.drawString(m + 1 * mm, y - 6 * mm, f"{p['nome']} - {doc_fmt}")
    c.drawString(m + 1 * mm, y - 10 * mm,
                 f"{p['endereco']} - {p['bairro']} - CEP {p['cep_prefixo']}-{p['cep_sufixo']} - {p['cidade']}/{p['uf']}")
    y -= 18 * mm

    # Separador tracejado (corte)
    c.setDash(2, 2)
    c.setStrokeGray(0.5)
    c.line(m, y, largura - m, y)
    c.setDash()
    c.setStrokeGray(0)
    y -= 3 * mm

    # ---------- FICHA DE COMPENSAÇÃO ----------
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m, y, "FICHA DE COMPENSACAO")
    y -= 6 * mm

    # Cabeçalho (Banco + Linha digitável)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(m, y - 5 * mm, "BANCO SAFRA S/A")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(m + 60 * mm, y - 5 * mm, f"| {CFG.BANCO}-{CFG.BANCO_DV}")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(largura - m, y - 5 * mm, ld)
    y -= 10 * mm

    # Local de pagamento + Vencimento
    caixa(m, y, largura - 2 * m - 60 * mm, 10 * mm)
    rotulo(m, y, "Local de pagamento")
    valor(m, y, "PAGAVEL EM QUALQUER BANCO DO SISTEMA DE COMPENSACAO", size=8)
    caixa(m + (largura - 2 * m - 60 * mm), y, 60 * mm, 10 * mm)
    rotulo(m + (largura - 2 * m - 60 * mm), y, "Vencimento")
    valor(m + (largura - 2 * m - 60 * mm), y, _fmt_data(titulo["data_vencimento"]), bold=True)
    y -= 10 * mm

    # Beneficiário + Ag/Cod Beneficiário
    caixa(m, y, largura - 2 * m - 60 * mm, 10 * mm)
    rotulo(m, y, "Beneficiario")
    valor(m, y,
          f"{CFG.RAZAO_SOCIAL} - CNPJ: {CFG.CNPJ[:2]}.{CFG.CNPJ[2:5]}.{CFG.CNPJ[5:8]}/{CFG.CNPJ[8:12]}-{CFG.CNPJ[12:]}",
          size=8)
    caixa(m + (largura - 2 * m - 60 * mm), y, 60 * mm, 10 * mm)
    rotulo(m + (largura - 2 * m - 60 * mm), y, "Agencia / Codigo Beneficiario")
    valor(m + (largura - 2 * m - 60 * mm), y, f"{CFG.AGENCIA} / {CFG.CONTA_COMPLETA}", bold=True)
    y -= 10 * mm

    # Data doc + Nº doc + Espécie + Aceite + Data process
    labels = [
        ("Data do Documento", _fmt_data(titulo["data_emissao"])),
        ("Nº do Documento", titulo["seu_numero"]),
        ("Especie Doc", "DM"),
        ("Aceite", "N"),
        ("Data Processamento", _fmt_data(date.today())),
    ]
    w = (largura - 2 * m - 60 * mm) / 5
    for i, (lab, val) in enumerate(labels):
        caixa(m + i * w, y, w, 10 * mm)
        rotulo(m + i * w, y, lab)
        valor(m + i * w, y, val, size=8)
    caixa(m + 5 * w, y, 60 * mm, 10 * mm)
    rotulo(m + 5 * w, y, "Nosso Numero")
    valor(m + 5 * w, y, titulo["nosso_numero"], bold=True)
    y -= 10 * mm

    # Uso do banco + Carteira + Espécie + Qtd + Valor + Valor do Documento
    labels = [
        ("Uso do Banco", ""),
        ("Carteira", CFG.CARTEIRA),
        ("Especie", "R$"),
        ("Quantidade", ""),
        ("(x) Valor", ""),
    ]
    for i, (lab, val) in enumerate(labels):
        caixa(m + i * w, y, w, 10 * mm)
        rotulo(m + i * w, y, lab)
        valor(m + i * w, y, val, size=8)
    caixa(m + 5 * w, y, 60 * mm, 10 * mm)
    rotulo(m + 5 * w, y, "(=) Valor do Documento")
    valor(m + 5 * w, y, _fmt_valor(titulo["valor_centavos"]), bold=True)
    y -= 10 * mm

    # Instruções (5 linhas) + campos financeiros
    caixa(m, y, largura - 2 * m - 60 * mm, 40 * mm)
    rotulo(m, y, "Instrucoes (texto de responsabilidade do beneficiario)")

    # Bloco de juros/multa em NEGRITO no topo do campo (visibilidade destacada)
    juros_multa_lns = []
    if titulo["juros_codigo"] == "1":
        v = titulo["juros_valor_centavos"] / 100.0
        juros_multa_lns.append(f"JUROS DE MORA: R$ {v:.2f} POR DIA APOS O VENCIMENTO".replace(".", ","))
    if titulo["multa_codigo"] == "2":
        juros_multa_lns.append(f"MULTA POR ATRASO: {titulo['multa_percentual']:.2f}%".replace(".", ","))

    c.setFont("Helvetica-Bold", 8)
    for i, ln in enumerate(juros_multa_lns):
        c.drawString(m + 1 * mm, y - 8 * mm - i * 4 * mm, ln)

    # Demais instrucoes em fonte normal, embaixo do bloco negrito
    c.setFont("Helvetica", 8)
    instr = [CFG.FRASE_INSTRUCOES_SAFRA]
    if titulo["desconto_codigo"] == "1":
        v = titulo["desconto_valor_centavos"] / 100.0
        instr.append(
            f"CONCEDER DESCONTO DE R$ {v:.2f} ATE {_fmt_data(titulo['desconto_data'])}".replace(".", ",")
        )
    if titulo["protesto_codigo"] == "3":
        instr.append("NAO PROTESTAR")
    if titulo["baixa_codigo"] == "1":
        instr.append(f"APOS {titulo['baixa_dias']} DIAS DO VENCIMENTO BAIXAR")

    base_offset = len(juros_multa_lns)
    for i, ln in enumerate(instr):
        c.drawString(m + 1 * mm, y - 8 * mm - (base_offset + i) * 4 * mm, ln)

    # Campos financeiros (direita)
    labs = [
        ("(-) Descontos / Abatimentos", ""),
        ("(-) Outras Deducoes", ""),
        ("(+) Mora / Multa", ""),
        ("(+) Outros Acrescimos", ""),
        ("(=) Valor Cobrado", ""),
    ]
    hh = 8 * mm
    for i, (lab, val) in enumerate(labs):
        caixa(m + (largura - 2 * m - 60 * mm), y - i * hh, 60 * mm, hh)
        rotulo(m + (largura - 2 * m - 60 * mm), y - i * hh, lab)
    y -= 40 * mm

    # Pagador
    caixa(m, y, largura - 2 * m, 14 * mm)
    rotulo(m, y, "Pagador")
    c.setFont("Helvetica", 9)
    c.drawString(m + 1 * mm, y - 6 * mm, f"{p['nome']} - {doc_fmt}")
    c.drawString(m + 1 * mm, y - 10 * mm,
                 f"{p['endereco']} - {p['bairro']} - CEP {p['cep_prefixo']}-{p['cep_sufixo']} - {p['cidade']}/{p['uf']}")
    y -= 18 * mm

    # Beneficiario Final (nomenclatura FEBRABAN obrigatoria - vazio quando nao ha sacador/avalista)
    caixa(m, y, largura - 2 * m, 8 * mm)
    rotulo(m, y, "Beneficiario Final")
    c.setFont("Helvetica", 9)
    c.drawString(m + 1 * mm, y - 6 * mm, "-")
    y -= 10 * mm

    # Autenticação mecânica + Ficha de Compensação
    c.setFont("Helvetica", 6)
    c.drawRightString(largura - m, y, "Ficha de Compensacao")
    y -= 5 * mm

    # Código de barras I2of5 (103mm × 13mm)
    barcode = I2of5(cod_barras, barWidth=0.30 * mm, barHeight=13 * mm,
                    quiet=False, checksum=0)
    barcode.drawOn(c, m, y - 13 * mm)

    c.showPage()
    c.save()


def _fmt_doc(doc, tipo):
    if tipo == "1":  # CPF
        return f"CPF: {doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
    return f"CNPJ: {doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"


if __name__ == "__main__":
    from titulos import TITULOS
    import os
    outdir = os.path.dirname(os.path.abspath(__file__))
    for t in TITULOS:
        cod = codigo_barras_44(t["nosso_numero"], t["data_vencimento"], t["valor_centavos"])
        ld = linha_digitavel(cod)
        print(f"NN {t['nosso_numero']}: CB={cod}  LD={ld}")
        pdf = os.path.join(outdir, f"boleto_{t['nosso_numero']}.pdf")
        gerar_boleto_pdf(t, pdf)
        print(f"  PDF: {pdf}")
