"""
Gera um .RET fictício simulando o retorno do Safra pros 3 títulos que
mandamos na remessa. Serve pra testar o parser retorno.py.

Cenários simulados:
  T1 (NN 000000001) -> ocorrencia 02 (Entrada confirmada)
  T2 (NN 000000002) -> ocorrencia 06 (Liquidação normal), pagou R$ 500 no vencimento
  T3 (NN 000000003) -> ocorrencia 03 (Entrada rejeitada), motivo 18 (data venc invalida)
"""

from datetime import date, timedelta
import config as CFG


def _alfa(v, tam):
    s = "" if v is None else str(v).upper()
    return s[:tam].ljust(tam)


def _num(v, tam):
    s = "" if v is None else str(v)
    return s[-tam:].rjust(tam, "0")


def _data(d):
    return d.strftime("%d%m%Y")


def _assert(l, tipo):
    if len(l) != 240:
        raise AssertionError(f"{tipo}: {len(l)} chars")
    return l


def header_arquivo(seq, dt):
    """0 - HA"""
    return _assert("".join([
        _num(CFG.BANCO, 3),                    # 001-003
        _num("0", 4),                          # 004-007
        _num("0", 1),                          # 008
        _alfa("", 9),                          # 009-017
        _num("2", 1),                          # 018
        _num(CFG.CNPJ, 14),                    # 019-032
        _alfa("", 20),                         # 033-052
        _num(CFG.AGENCIA, 5),                  # 053-057
        _alfa("", 1),                          # 058
        _num(CFG.CONTA_NUMERO, 12),            # 059-070
        _alfa(CFG.CONTA_DV, 1),                # 071
        _alfa("", 1),                          # 072
        _alfa(CFG.RAZAO_SOCIAL, 30),           # 073-102
        _alfa("BANCO SAFRA S/A", 30),          # 103-132
        _alfa("", 10),                         # 133-142
        _num("2", 1),                          # 143 = Codigo Retorno
        _num(_data(dt), 8),                    # 144-151
        _num("0", 6),                          # 152-157
        _num(seq, 6),                          # 158-163
        _num(CFG.LAYOUT_VERSAO_ARQUIVO, 3),    # 164-166
        _alfa("", 5),                          # 167-171
        _alfa("", 20),                         # 172-191
        _alfa("", 20),                         # 192-211
        _alfa("", 29),                         # 212-240
    ]), "HA")


def header_lote(lote, dt):
    """1 - HL"""
    return _assert("".join([
        _num(CFG.BANCO, 3),                    # 001-003
        _num(lote, 4),                         # 004-007
        _num("1", 1),                          # 008
        _alfa("T", 1),                         # 009 = T (Retorno)
        _num("01", 2),                         # 010-011
        _alfa("", 2),                          # 012-013
        _num(CFG.LAYOUT_VERSAO_LOTE, 3),       # 014-016
        _alfa("", 1),                          # 017
        _num("2", 1),                          # 018
        _num(CFG.CNPJ, 15),                    # 019-033
        _alfa("", 20),                         # 034-053
        _num(CFG.AGENCIA, 5),                  # 054-058
        _alfa("", 1),                          # 059
        _num(CFG.CONTA_NUMERO, 12),            # 060-071
        _alfa(CFG.CONTA_DV, 1),                # 072
        _alfa("", 1),                          # 073
        _alfa(CFG.RAZAO_SOCIAL, 30),           # 074-103
        _alfa("", 40),                         # 104-143
        _alfa("", 40),                         # 144-183
        _num("1", 8),                          # 184-191
        _num(_data(dt), 8),                    # 192-199
        _num("0", 8),                          # 200-207
        _alfa("", 33),                         # 208-240
    ]), "HL")


def segmento_t(lote, seq, nn, seu_num, valor_cent, ocorrencia, motivos5,
               pagador_tipo_ins="1", pagador_doc="52998224725", pagador_nome="JOSE TESTE"):
    """3T - dados titulo (FEBRABAN 240)"""
    # Preenche até 5 motivos (10 chars total)
    mot_str = "".join(m.ljust(2, "0") for m in (motivos5 + ["00"] * 5)[:5])
    return _assert("".join([
        _num(CFG.BANCO, 3),                    # 001-003
        _num(lote, 4),                         # 004-007
        _num("3", 1),                          # 008
        _num(seq, 5),                          # 009-013
        _alfa("T", 1),                         # 014
        _alfa("", 1),                          # 015
        _num(ocorrencia, 2),                   # 016-017
        _num(CFG.AGENCIA, 5),                  # 018-022
        _alfa("", 1),                          # 023
        _num(CFG.CONTA_NUMERO, 12),            # 024-035
        _alfa(CFG.CONTA_DV, 1),                # 036
        _alfa("", 1),                          # 037
        _num(nn, 9) + _alfa("", 11),           # 038-057 NN 20 chars (9 + 11 brancos)
        _alfa(CFG.CARTEIRA, 1),                # 058
        _alfa(seu_num, 15),                    # 059-073 Num Documento
        _num(_data(date.today() + timedelta(days=30)), 8),  # 074-081 Data Venc
        _num(valor_cent, 15),                  # 082-096 Valor Titulo
        _num(CFG.BANCO, 3),                    # 097-099 Banco Cobrador
        _num(CFG.AGENCIA, 5),                  # 100-104 Ag Cobradora
        _alfa("", 1),                          # 105
        _alfa(seu_num, 25),                    # 106-130 Ident Titulo Empresa
        _num(pagador_tipo_ins, 1),             # 131
        _num(pagador_doc, 15),                 # 132-146 CPF/CNPJ Sacado
        _alfa(pagador_nome, 40),               # 147-186
        _alfa("", 12),                         # 187-198 Num Contrato
        _num("0", 15),                         # 199-213 Valor Tarifa
        _alfa(mot_str, 10),                    # 214-223 Motivos
        _alfa("", 17),                         # 224-240 CNAB
    ]), f"T {nn}")


def segmento_u(lote, seq, ocorrencia, juros_cent, valor_pago_cent, valor_liq_cent, dt_ocorr, dt_cred):
    """3U - valores liquidacao"""
    return _assert("".join([
        _num(CFG.BANCO, 3),                    # 001-003
        _num(lote, 4),                         # 004-007
        _num("3", 1),                          # 008
        _num(seq, 5),                          # 009-013
        _alfa("U", 1),                         # 014
        _alfa("", 1),                          # 015
        _num(ocorrencia, 2),                   # 016-017
        _num(juros_cent, 15),                  # 018-032 Juros/Multa
        _num("0", 15),                         # 033-047 Desconto
        _num("0", 15),                         # 048-062 Abatimento
        _num("0", 15),                         # 063-077 IOF
        _num(valor_pago_cent, 15),             # 078-092 Valor Pago
        _num(valor_liq_cent, 15),              # 093-107 Valor Liq
        _num("0", 15),                         # 108-122 Outras Desp
        _num("0", 15),                         # 123-137 Outros Cred
        _num(_data(dt_ocorr), 8) if dt_ocorr else _num("0", 8),  # 138-145 Data Ocorr
        _num(_data(dt_cred), 8) if dt_cred else _num("0", 8),    # 146-153 Data Credito
        _alfa("", 4),                          # 154-157 Cod Ocorr Pagador
        _num("0", 8),                          # 158-165 Data Ocorr Pagador
        _num("0", 15),                         # 166-180 Valor Ocorr Pagador
        _alfa("", 30),                         # 181-210 Complemento
        _num("0", 3),                          # 211-213 Banco Corresp
        _alfa("", 20),                         # 214-233 NN Correspondente
        _alfa("", 7),                          # 234-240 CNAB
    ]), f"U seq{seq}")


def trailer_lote(lote, qtd_reg, qtd_tit, valor_tot):
    return _assert("".join([
        _num(CFG.BANCO, 3), _num(lote, 4), _num("5", 1), _alfa("", 9),
        _num(qtd_reg, 6), _num(qtd_tit, 6), _num(valor_tot, 17),
        _num("0", 6), _num("0", 17), _num("0", 6), _num("0", 17),
        _num("0", 6), _num("0", 17), _alfa("", 8), _alfa("", 117),
    ]), "TL")


def trailer_arquivo(qtd_lotes, qtd_reg):
    return _assert("".join([
        _num(CFG.BANCO, 3), _num("9999", 4), _num("9", 1), _alfa("", 9),
        _num(qtd_lotes, 6), _num(qtd_reg, 6), _num("0", 6), _alfa("", 205),
    ]), "TA")


def gerar_ret_sample():
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    linhas = []

    linhas.append(header_arquivo(1, hoje))
    linhas.append(header_lote(1, hoje))

    # T1 confirmado (ocorr 02)
    linhas.append(segmento_t(1, 1, "000000001", "TESTE00001", 10000, "02", ["00"],
                             pagador_tipo_ins="1", pagador_doc="52998224725",
                             pagador_nome="JOSE DA SILVA TESTE"))
    linhas.append(segmento_u(1, 2, "02", 0, 0, 0, hoje, None))

    # T2 liquidado (ocorr 06)
    linhas.append(segmento_t(1, 3, "000000002", "TESTE00002", 50000, "06", ["00"],
                             pagador_tipo_ins="1", pagador_doc="31628382821",
                             pagador_nome="MARIA APARECIDA TESTE"))
    linhas.append(segmento_u(1, 4, "06", 0, 50000, 49985, ontem, hoje))

    # T3 rejeitado (ocorr 03, motivo 18)
    linhas.append(segmento_t(1, 5, "000000003", "TESTE00003", 123456, "03", ["18"],
                             pagador_tipo_ins="2", pagador_doc="45283163000167",
                             pagador_nome="CONFECCOES TESTE HOMOLOG LTDA"))
    linhas.append(segmento_u(1, 6, "03", 0, 0, 0, hoje, None))

    qtd_reg_detalhe = 6
    qtd_reg_lote = qtd_reg_detalhe + 2
    linhas.append(trailer_lote(1, qtd_reg_lote, 3, 10000 + 50000 + 123456))
    linhas.append(trailer_arquivo(1, len(linhas) + 1))

    return "\r\n".join(linhas) + "\r\n"


if __name__ == "__main__":
    import os
    conteudo = gerar_ret_sample()
    outdir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(outdir, exist_ok=True)
    caminho = os.path.join(outdir, "SAMPLE_RETORNO.RET")
    with open(caminho, "w") as f:
        f.write(conteudo)
    print(f"Gerado: {caminho}")
    print(f"Linhas: {len(conteudo.splitlines())}, bytes: {len(conteudo)}")
