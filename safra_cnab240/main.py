"""
Gera o arquivo remessa .REM + os 3 PDFs de boleto pra homologação Safra.
Valida internamente antes de escrever no disco.

Uso: python3 main.py

Saída:
  output/SOUL_INDUST_355_TESTE.REM
  output/boleto_000000001.pdf
  output/boleto_000000002.pdf
  output/boleto_000000003.pdf
"""

import os
from datetime import date

import config as CFG
from titulos import TITULOS
from cnab240 import gerar_remessa
from boleto import codigo_barras_44, linha_digitavel, gerar_boleto_pdf


AQUI = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(AQUI, "output")
os.makedirs(OUTDIR, exist_ok=True)


def validar_rem(conteudo):
    """Validações básicas do arquivo REM antes de enviar."""
    linhas = conteudo.splitlines()
    erros = []

    # 1. Cada linha 240 chars
    for i, l in enumerate(linhas, 1):
        if len(l) != 240:
            erros.append(f"Linha {i}: {len(l)} chars (esperado 240)")

    # 2. Estrutura: Header Arq (0) + Header Lote (1) + N*(P+Q+[R]) + Trailer Lote (5) + Trailer Arq (9)
    if linhas[0][7] != "0":
        erros.append(f"Linha 1 nao e Header Arquivo (tipo {linhas[0][7]})")
    if linhas[1][7] != "1":
        erros.append(f"Linha 2 nao e Header Lote (tipo {linhas[1][7]})")
    if linhas[-1][7] != "9":
        erros.append(f"Ultima linha nao e Trailer Arquivo (tipo {linhas[-1][7]})")
    if linhas[-2][7] != "5":
        erros.append(f"Penultima linha nao e Trailer Lote (tipo {linhas[-2][7]})")

    # 3. Ag/Conta iguais em Header Arq, Header Lote e Segmento P
    ag_ha = linhas[0][52:57]
    cnt_ha = linhas[0][58:70]
    dv_ha = linhas[0][70]
    ag_hl = linhas[1][53:58]
    cnt_hl = linhas[1][59:71]
    dv_hl = linhas[1][71]
    if ag_ha != ag_hl:
        erros.append(f"Agencia divergente: HA={ag_ha} HL={ag_hl}")
    if cnt_ha != cnt_hl:
        erros.append(f"Conta divergente: HA={cnt_ha} HL={cnt_hl}")
    if dv_ha != dv_hl:
        erros.append(f"DV divergente: HA={dv_ha} HL={dv_hl}")

    # Percorre os segmentos detalhe, aceita P, Q, R
    qtd_p = qtd_q = qtd_r = 0
    for i in range(2, len(linhas) - 2):
        seg = linhas[i][13]
        if seg == "P":
            qtd_p += 1
            if linhas[i][17:22] != ag_ha:
                erros.append(f"Linha {i+1}: Agencia SegP != HA")
            if linhas[i][23:35] != cnt_ha:
                erros.append(f"Linha {i+1}: Conta SegP != HA")
            if linhas[i][46:57] != " " * 11:
                erros.append(f"Linha {i+1}: pos 47-57 devem estar em branco")
        elif seg == "Q":
            qtd_q += 1
        elif seg == "R":
            qtd_r += 1
        else:
            erros.append(f"Linha {i+1}: segmento inesperado '{seg}'")

    # 4. Trailer Lote
    tl = linhas[-2]
    qtd_r_esperado = sum(1 for t in TITULOS if t.get("multa_codigo", "0") != "0")
    qtd_lote_esperado = 2 + 2 * len(TITULOS) + qtd_r_esperado
    qtd_lote_lido = int(tl[17:23])
    if qtd_lote_lido != qtd_lote_esperado:
        erros.append(f"Trailer Lote: qtd {qtd_lote_lido} != esperado {qtd_lote_esperado}")
    qtd_tit_esperado = len(TITULOS)
    qtd_tit_lido = int(tl[23:29])
    if qtd_tit_lido != qtd_tit_esperado:
        erros.append(f"Trailer Lote: qtd titulos {qtd_tit_lido} != {qtd_tit_esperado}")
    valor_total_esperado = sum(t["valor_centavos"] for t in TITULOS)
    valor_total_lido = int(tl[29:46])
    if valor_total_lido != valor_total_esperado:
        erros.append(f"Trailer Lote: valor total {valor_total_lido} != {valor_total_esperado}")

    # Confere contadores P/Q/R
    if qtd_p != len(TITULOS):
        erros.append(f"Qtd Seg P {qtd_p} != {len(TITULOS)}")
    if qtd_q != len(TITULOS):
        erros.append(f"Qtd Seg Q {qtd_q} != {len(TITULOS)}")
    if qtd_r != qtd_r_esperado:
        erros.append(f"Qtd Seg R {qtd_r} != {qtd_r_esperado}")

    # 5. Trailer Arquivo
    ta = linhas[-1]
    qtd_arq_esperado = len(linhas)
    qtd_arq_lido = int(ta[23:29])
    if qtd_arq_lido != qtd_arq_esperado:
        erros.append(f"Trailer Arquivo: qtd registros {qtd_arq_lido} != {qtd_arq_esperado}")

    return erros


def main():
    print("=" * 60)
    print(f"SOUL INDUST 355 - Homologacao Safra CNAB 240")
    print(f"CNPJ: {CFG.CNPJ}   Ag/Conta: {CFG.AGENCIA}/{CFG.CONTA_COMPLETA}")
    print(f"Carteira: {CFG.CARTEIRA}   Layout: {CFG.LAYOUT_VERSAO_ARQUIVO}")
    print("=" * 60)

    # 1. Gerar REM
    print("\n[1] Gerando arquivo remessa...")
    rem = gerar_remessa(TITULOS)
    hoje_str = date.today().strftime("%d%m%Y")
    caminho_rem = os.path.join(OUTDIR, f"SOUL_INDUST_355_{hoje_str}_n3.REM")
    with open(caminho_rem, "w", newline="") as f:
        f.write(rem)
    print(f"    -> {caminho_rem}")
    print(f"    -> {len(rem.splitlines())} linhas, {len(rem)} bytes")

    # 2. Validar
    print("\n[2] Validando estrutura...")
    erros = validar_rem(rem)
    if erros:
        print("    !! ERROS encontrados:")
        for e in erros:
            print(f"    - {e}")
        return
    print("    OK - todas as validacoes passaram")

    # 3. Gerar boletos
    print("\n[3] Gerando boletos PDF...")
    for t in TITULOS:
        cod = codigo_barras_44(t["nosso_numero"], t["data_vencimento"], t["valor_centavos"])
        ld = linha_digitavel(cod)
        pdf = os.path.join(OUTDIR, f"SOUL_INDUST_355_{hoje_str}_n3_boleto_{t['nosso_numero']}.pdf")
        gerar_boleto_pdf(t, pdf)
        p = t["pagador"]
        doc = p["cpf_cnpj"]
        print(f"    NN {t['nosso_numero']}  R$ {t['valor_centavos']/100:>10,.2f}"
              f"  venc {t['data_vencimento'].strftime('%d/%m/%Y')}"
              f"  pagador {p['nome'][:25]}")
        print(f"      CB: {cod}")
        print(f"      LD: {ld}")
        print(f"      -> {pdf}")

    print("\n" + "=" * 60)
    print("PRONTO. Anexar ao email pra mesa.implantacao@safra.com.br:")
    print(f"  - {caminho_rem}")
    for t in TITULOS:
        nn = t["nosso_numero"]
        print(f"  - {os.path.join(OUTDIR, f'SOUL_INDUST_355_{hoje_str}_n3_boleto_{nn}.pdf')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
