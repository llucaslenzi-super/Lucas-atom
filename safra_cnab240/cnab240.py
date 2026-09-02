"""
Gerador de arquivo remessa CNAB 240 - Layout Padrão Safra (agosto/2026).

Cada linha do arquivo tem exatamente 240 caracteres.

Estrutura do arquivo pra N títulos:
  Linha 1     : Header Arquivo   (Tipo 0)
  Linha 2     : Header Lote      (Tipo 1)
  Linhas 3..k : Segmentos P e Q  (Tipo 3, dois por título)
  Linha k+1   : Trailer Lote     (Tipo 5)
  Linha k+2   : Trailer Arquivo  (Tipo 9)

Total = 4 + 2N linhas
"""

from datetime import date
import config as CFG


# ---------- Helpers ----------

def _alfa(valor, tam):
    """Campo alfanumérico: caixa alta, à esquerda, brancos à direita."""
    s = "" if valor is None else str(valor)
    s = s.upper()
    return s[:tam].ljust(tam)


def _num(valor, tam):
    """Campo numérico: zeros à esquerda."""
    s = "" if valor is None else str(valor)
    return s[-tam:].rjust(tam, "0")


def _data(d):
    """Data DDMMAAAA."""
    return d.strftime("%d%m%Y")


def _assert(linha, tipo):
    if len(linha) != 240:
        raise AssertionError(f"{tipo}: linha tem {len(linha)} chars, esperado 240")
    return linha


# ---------- Registros ----------

def header_arquivo(seq_arquivo, data_geracao):
    """Registro Tipo 0 - Header de Arquivo (240 chars)."""
    parts = [
        _num(CFG.BANCO, 3),                          # 001-003 Banco
        _num("0", 4),                                # 004-007 Lote = 0000
        _num("0", 1),                                # 008     Tipo Registro = 0
        _alfa("", 9),                                # 009-017 CNAB brancos
        _num("2", 1),                                # 018     Tipo Insc = 2 (CNPJ)
        _num(CFG.CNPJ, 14),                          # 019-032 CNPJ
        _alfa("", 20),                               # 033-052 Convênio (brancos)
        _num(CFG.AGENCIA, 5),                        # 053-057 Agência
        _alfa("", 1),                                # 058     DV Agência (branco)
        _num(CFG.CONTA_NUMERO, 12),                  # 059-070 Conta
        _alfa(CFG.CONTA_DV, 1),                      # 071     DV Conta
        _alfa("", 1),                                # 072     DV Ag/Conta (branco)
        _alfa(CFG.RAZAO_SOCIAL, 30),                 # 073-102 Nome Empresa
        _alfa("BANCO SAFRA S/A", 30),                # 103-132 Nome Banco
        _alfa("", 10),                               # 133-142 CNAB brancos
        _num("1", 1),                                # 143     Código Remessa = 1
        _num(_data(data_geracao), 8),                # 144-151 Data Geração
        _num("0", 6),                                # 152-157 Hora = 000000
        _num(seq_arquivo, 6),                        # 158-163 Sequencial Arquivo
        _num(CFG.LAYOUT_VERSAO_ARQUIVO, 3),          # 164-166 Versão Layout
        _alfa("", 5),                                # 167-171 Densidade (brancos)
        _alfa("", 20),                               # 172-191 Uso Banco (brancos)
        _alfa("", 20),                               # 192-211 Uso Empresa (brancos)
        _alfa("", 29),                               # 212-240 CNAB brancos
    ]
    return _assert("".join(parts), "Header Arquivo")


def header_lote(numero_lote, data_geracao):
    """Registro Tipo 1 - Header de Lote (240 chars)."""
    parts = [
        _num(CFG.BANCO, 3),                          # 001-003 Banco
        _num(numero_lote, 4),                        # 004-007 Lote
        _num("1", 1),                                # 008     Tipo Registro = 1
        _alfa("R", 1),                               # 009     Operação = R (Remessa)
        _num("01", 2),                               # 010-011 Serviço = 01 (Cobrança)
        _alfa("", 2),                                # 012-013 CNAB brancos
        _num(CFG.LAYOUT_VERSAO_LOTE, 3),             # 014-016 Versão Layout Lote
        _alfa("", 1),                                # 017     CNAB branco
        _num("2", 1),                                # 018     Tipo Insc = 2 (CNPJ)
        _num(CFG.CNPJ, 15),                          # 019-033 CNPJ 15 pos numerico (zero a esquerda)
        _alfa("", 20),                               # 034-053 Convênio (brancos)
        _num(CFG.AGENCIA, 5),                        # 054-058 Agência
        _alfa("", 1),                                # 059     DV Agência (branco)
        _num(CFG.CONTA_NUMERO, 12),                  # 060-071 Conta
        _alfa(CFG.CONTA_DV, 1),                      # 072     DV Conta
        _alfa("", 1),                                # 073     DV Ag/Conta (branco)
        _alfa(CFG.RAZAO_SOCIAL, 30),                 # 074-103 Nome Empresa
        _alfa("", 40),                               # 104-143 Mensagem 1 (branco)
        _alfa("", 40),                               # 144-183 Mensagem 2 (branco)
        _num("1", 8),                                # 184-191 Nº Remessa
        _num(_data(data_geracao), 8),                # 192-199 Data Gravação
        _num("0", 8),                                # 200-207 Data Crédito = 0
        _alfa("", 33),                               # 208-240 CNAB brancos
    ]
    return _assert("".join(parts), "Header Lote")


def segmento_p(numero_lote, seq_registro, titulo):
    """Registro Tipo 3 Segmento P - Dados do título (240 chars).

    Aceita `titulo["codigo_movimento"]` pra escolher a operacao (default '01').
    """
    _codmov = titulo.get("codigo_movimento", "01")
    # Nosso Número: 9 posições livres em 38-46; 47-57 em branco (Safra ignora)
    nosso_numero_20 = _num(titulo["nosso_numero"], 9) + _alfa("", 11)

    # Regra Safra: se cobrar juros (código '1'), data juros deve ser >= vencimento
    # e valor > 0. Se isento (código '3'), data e valor obrigatoriamente ZERADOS.
    if titulo["juros_codigo"] == "3":
        juros_data_str = "00000000"
        juros_valor = 0
    else:
        juros_data_str = _data(titulo["juros_data"])
        juros_valor = titulo["juros_valor_centavos"]

    # Mesma regra pra desconto: código '0' força data e valor zerados
    if titulo["desconto_codigo"] == "0":
        desconto_data_str = "00000000"
        desconto_valor = 0
    else:
        desconto_data_str = _data(titulo["desconto_data"])
        desconto_valor = titulo["desconto_valor_centavos"]

    parts = [
        _num(CFG.BANCO, 3),                          # 001-003 Banco
        _num(numero_lote, 4),                        # 004-007 Lote
        _num("3", 1),                                # 008     Tipo Registro = 3
        _num(seq_registro, 5),                       # 009-013 Sequencial
        _alfa("P", 1),                               # 014     Segmento = P
        _alfa("", 1),                                # 015     CNAB branco
        _num(_codmov, 2),                            # 016-017 Cód Movimento
        _num(CFG.AGENCIA, 5),                        # 018-022 Agência
        _alfa("", 1),                                # 023     DV Agência (branco)
        _num(CFG.CONTA_NUMERO, 12),                  # 024-035 Conta
        _alfa(CFG.CONTA_DV, 1),                      # 036     DV Conta
        _alfa("", 1),                                # 037     DV Ag/Conta (branco)
        nosso_numero_20,                             # 038-057 Nosso Número (9 + 11 brancos)
        _num(CFG.CARTEIRA, 1),                       # 058     Carteira = 1
        _num(CFG.CADASTRO_TITULO, 1),                # 059     Cadastro = 1 (Registrada)
        _alfa(CFG.TIPO_DOCUMENTO, 1),                # 060     Tipo Doc = 2 (Escritural)
        _num(CFG.IDENTIFICACAO_BLOQUETO, 1),         # 061     Emissão = 2 (Cliente)
        _alfa(CFG.DISTRIBUICAO_BLOQUETO, 1),         # 062     Distribuição = 2 (Cliente)
        _alfa(titulo["seu_numero"], 15),             # 063-077 Nº Documento (Seu Número)
        _num(_data(titulo["data_vencimento"]), 8),   # 078-085 Data Vencimento
        _num(titulo["valor_centavos"], 15),          # 086-100 Valor Nominal
        _num(CFG.AGENCIA, 5),                        # 101-105 Ag Cobradora
        _alfa("", 1),                                # 106     DV Ag Cobradora (branco)
        _num(titulo["especie"], 2),                  # 107-108 Espécie
        _alfa("N", 1),                               # 109     Aceite = N
        _num(_data(titulo["data_emissao"]), 8),      # 110-117 Data Emissão
        _num(titulo["juros_codigo"], 1),             # 118     Cód Juros Mora
        _num(juros_data_str, 8),                     # 119-126 Data Juros (0 se isento)
        _num(juros_valor, 15),                       # 127-141 Juros Mora/Dia (0 se isento)
        _num(titulo["desconto_codigo"], 1),          # 142     Cód Desconto 1
        _num(desconto_data_str, 8),                  # 143-150 Data Desconto (0 se sem desconto)
        _num(desconto_valor, 15),                    # 151-165 Valor Desconto (0 se sem desconto)
        _num("0", 15),                               # 166-180 Valor IOF = 0
        _num("0", 15),                               # 181-195 Valor Abatimento = 0
        _alfa(titulo["seu_numero"], 25),             # 196-220 Uso Empresa (livre)
        _num(titulo["protesto_codigo"], 1),          # 221     Cód Protesto
        _num(titulo["protesto_dias"], 2),            # 222-223 Dias Protesto
        _num(titulo["baixa_codigo"], 1),             # 224     Cód Baixa
        _alfa(_num(titulo["baixa_dias"], 3), 3),     # 225-227 Dias Baixa (alfa no manual)
        _num("09", 2),                               # 228-229 Moeda = 09 (Real)
        _num("0", 10),                               # 230-239 Nº Contrato = 0
        _alfa("1", 1),                               # 240     Uso Livre = 1 (não parcial)
    ]
    return _assert("".join(parts), f"Segmento P {titulo['nosso_numero']}")


def segmento_q(numero_lote, seq_registro, titulo):
    """Registro Tipo 3 Segmento Q - Dados do pagador (240 chars)."""
    p = titulo["pagador"]
    _codmov = titulo.get("codigo_movimento", "01")
    parts = [
        _num(CFG.BANCO, 3),                          # 001-003 Banco
        _num(numero_lote, 4),                        # 004-007 Lote
        _num("3", 1),                                # 008     Tipo Registro
        _num(seq_registro, 5),                       # 009-013 Sequencial
        _alfa("Q", 1),                               # 014     Segmento = Q
        _alfa("", 1),                                # 015     CNAB branco
        _num(_codmov, 2),                            # 016-017 Cód Movimento
        _num(p["tipo_inscricao"], 1),                # 018     Tipo Insc Pagador
        _num(p["cpf_cnpj"], 15),                     # 019-033 CPF/CNPJ 15 pos numerico
        _alfa(p["nome"], 40),                        # 034-073 Nome Pagador
        _alfa(p["endereco"], 40),                    # 074-113 Endereço
        _alfa(p["bairro"], 15),                      # 114-128 Bairro
        _num(p["cep_prefixo"], 5),                   # 129-133 CEP
        _num(p["cep_sufixo"], 3),                    # 134-136 Sufixo CEP
        _alfa(p["cidade"], 15),                      # 137-151 Cidade
        _alfa(p["uf"], 2),                           # 152-153 UF
        _num("0", 1),                                # 154     Tipo Insc Sacador = 0
        _num("0", 15),                               # 155-169 Nº Insc Sacador = 15 zeros
        _alfa("", 40),                               # 170-209 Nome Sacador (branco)
        _num("0", 3),                                # 210-212 Bco Correspondente = 0
        _alfa("", 20),                               # 213-232 N/N Correspondente (branco)
        _alfa("", 8),                                # 233-240 CNAB brancos
    ]
    return _assert("".join(parts), f"Segmento Q {titulo['nosso_numero']}")


def segmento_r(numero_lote, seq_registro, titulo):
    """Registro Tipo 3 Segmento R - Multa e Descontos 2/3 (240 chars).

    Só emitido quando titulo tem multa (multa_codigo != '0').
    Descontos 2 e 3 sempre zerados (Safra não trata).
    """
    _codmov = titulo.get("codigo_movimento", "01")
    parts = [
        _num(CFG.BANCO, 3),                          # 001-003 Banco
        _num(numero_lote, 4),                        # 004-007 Lote
        _num("3", 1),                                # 008     Tipo Registro
        _num(seq_registro, 5),                       # 009-013 Sequencial
        _alfa("R", 1),                               # 014     Segmento = R
        _alfa("", 1),                                # 015     CNAB branco
        _num(_codmov, 2),                            # 016-017 Cód Movimento
        _num("0", 1),                                # 018     Cód Desc 2 (Safra ignora)
        _num("0", 8),                                # 019-026 Data Desc 2 = 0
        _num("0", 15),                               # 027-041 Valor Desc 2 = 0
        _num("0", 1),                                # 042     Cód Desc 3
        _num("0", 8),                                # 043-050 Data Desc 3 = 0
        _num("0", 15),                               # 051-065 Valor Desc 3 = 0
        _num(titulo["multa_codigo"], 1),             # 066     Cód Multa
        _num(_data(titulo["multa_data"]), 8),        # 067-074 Data Multa
        # 075-089 Percentual Multa (15 chars, 2 dec implicitos)
        _num(int(round(titulo["multa_percentual"] * 100)), 15),
        _alfa("", 10),                               # 090-099 Informação Pagador (branco)
        _alfa("", 40),                               # 100-139 Mensagem 3 (branco)
        _alfa("", 40),                               # 140-179 Mensagem 4 (branco)
        _alfa("", 20),                               # 180-199 CNAB brancos
        _alfa("", 8),                                # 200-207 Cód Ocorr Pagador (branco)
        _alfa("", 3),                                # 208-210 Bco Débito (branco)
        _alfa("", 5),                                # 211-215 Ag Débito (branco)
        _alfa("", 1),                                # 216     DV Ag Débito (branco)
        _alfa("", 12),                               # 217-228 Conta Débito (branco)
        _alfa("", 1),                                # 229     DV Conta Débito (branco)
        _alfa("", 1),                                # 230     DV Ag/Conta Débito (branco)
        _alfa("", 1),                                # 231     Aviso Débito Auto (branco)
        _alfa("", 9),                                # 232-240 CNAB brancos
    ]
    return _assert("".join(parts), f"Segmento R {titulo['nosso_numero']}")


def trailer_lote(numero_lote, qtd_registros_detalhe, qtd_titulos, valor_total_centavos):
    """Registro Tipo 5 - Trailer de Lote (240 chars).

    qtd_registros_detalhe = total de P+Q+R+S (registros tipo 3) no lote
    """
    parts = [
        _num(CFG.BANCO, 3),                          # 001-003 Banco
        _num(numero_lote, 4),                        # 004-007 Lote
        _num("5", 1),                                # 008     Tipo Registro = 5
        _alfa("", 9),                                # 009-017 CNAB brancos
        _num(qtd_registros_detalhe, 6),              # 018-023 Qtd Registros Lote
        _num(qtd_titulos, 6),                        # 024-029 Qtd Cobrança Simples
        _num(valor_total_centavos, 17),              # 030-046 Valor Total Simples
        _num("0", 6),                                # 047-052 Qtd Vinculada
        _num("0", 17),                               # 053-069 Valor Vinculada
        _num("0", 6),                                # 070-075 Qtd Caucionada
        _num("0", 17),                               # 076-092 Valor Caucionada
        _num("0", 6),                                # 093-098 Qtd Descontada
        _num("0", 17),                               # 099-115 Valor Descontada
        _alfa("", 8),                                # 116-123 Nº Aviso (branco)
        _alfa("", 117),                              # 124-240 CNAB brancos
    ]
    return _assert("".join(parts), "Trailer Lote")


def trailer_arquivo(qtd_lotes, qtd_registros_arquivo):
    """Registro Tipo 9 - Trailer de Arquivo (240 chars)."""
    parts = [
        _num(CFG.BANCO, 3),                          # 001-003 Banco
        _num("9999", 4),                             # 004-007 Lote = 9999
        _num("9", 1),                                # 008     Tipo Registro = 9
        _alfa("", 9),                                # 009-017 CNAB brancos
        _num(qtd_lotes, 6),                          # 018-023 Qtd Lotes
        _num(qtd_registros_arquivo, 6),              # 024-029 Qtd Registros Arquivo
        _num("0", 6),                                # 030-035 Qtd Contas Concil.
        _alfa("", 205),                              # 036-240 CNAB brancos
    ]
    return _assert("".join(parts), "Trailer Arquivo")


# ---------- Gerador Principal ----------

def gerar_remessa(titulos, seq_arquivo=1, data_geracao=None):
    """Retorna string com o arquivo remessa completo (linhas separadas por \\r\\n)."""
    if data_geracao is None:
        data_geracao = date.today()

    linhas = []
    numero_lote = 1

    linhas.append(header_arquivo(seq_arquivo, data_geracao))
    linhas.append(header_lote(numero_lote, data_geracao))

    seq = 0
    valor_total = 0
    qtd_registros_detalhe = 0
    for t in titulos:
        seq += 1
        linhas.append(segmento_p(numero_lote, seq, t))
        qtd_registros_detalhe += 1
        seq += 1
        linhas.append(segmento_q(numero_lote, seq, t))
        qtd_registros_detalhe += 1
        # Segmento R só emitido se houver multa (multa_codigo != '0')
        if t.get("multa_codigo", "0") != "0":
            seq += 1
            linhas.append(segmento_r(numero_lote, seq, t))
            qtd_registros_detalhe += 1
        valor_total += t["valor_centavos"]

    qtd_registros_lote_total = qtd_registros_detalhe + 2  # + Header Lote + Trailer Lote
    linhas.append(trailer_lote(
        numero_lote,
        qtd_registros_lote_total,  # G057: soma dos tipos 1,2,3,4,5
        len(titulos),
        valor_total,
    ))

    qtd_registros_arquivo = len(linhas) + 1  # + o Trailer Arquivo que vai entrar
    linhas.append(trailer_arquivo(1, qtd_registros_arquivo))

    return "\r\n".join(linhas) + "\r\n"


# ---------- Wrappers de movimento ----------

def _clone(t, cod_mov):
    novo = dict(t)
    novo["codigo_movimento"] = cod_mov
    return novo


def gerar_remessa_entrada(titulos, seq_arquivo=1, data_geracao=None):
    """Cod 01 - Entrada de titulos (default)."""
    return gerar_remessa([_clone(t, "01") for t in titulos], seq_arquivo, data_geracao)


def gerar_remessa_baixa(titulos, seq_arquivo=1, data_geracao=None):
    """Cod 02 - Pedido de baixa."""
    return gerar_remessa([_clone(t, "02") for t in titulos], seq_arquivo, data_geracao)


def gerar_remessa_alteracao_venc(titulos, seq_arquivo=1, data_geracao=None):
    """Cod 06 - Alteracao de vencimento (titulo["data_vencimento"] = novo)."""
    return gerar_remessa([_clone(t, "06") for t in titulos], seq_arquivo, data_geracao)


def gerar_remessa_alteracao_dados(titulos, seq_arquivo=1, data_geracao=None):
    """Cod 31 - Alteracao outros dados (juros/multa/desconto)."""
    return gerar_remessa([_clone(t, "31") for t in titulos], seq_arquivo, data_geracao)


def gerar_remessa_protesto(titulos, seq_arquivo=1, data_geracao=None):
    """Cod 09 - Pedido de protesto."""
    return gerar_remessa([_clone(t, "09") for t in titulos], seq_arquivo, data_geracao)


def gerar_remessa_sustar_protesto(titulos, seq_arquivo=1, data_geracao=None):
    """Cod 10 - Sustar protesto."""
    return gerar_remessa([_clone(t, "10") for t in titulos], seq_arquivo, data_geracao)


if __name__ == "__main__":
    from titulos import TITULOS
    arquivo = gerar_remessa(TITULOS)
    print(arquivo)
    print(f"\n=== {len(arquivo.splitlines())} linhas geradas ===")
    for i, l in enumerate(arquivo.splitlines(), 1):
        print(f"Linha {i}: {len(l)} chars {'OK' if len(l) == 240 else 'ERRO'}")
