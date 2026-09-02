"""
Dados fixos para geração do arquivo remessa + boletos SOUL INDUST 355.
Fonte: emails Safra + endereço confirmado pelo cliente.

Interpretação da conta (extraída do manual CNAB 240 Safra, item 3 TESTES):
  "5 posições para a agência (sem dígito) e nove posições para a conta (com dígito)"

  Conta enviada pelo Safra: 005875216 (9 chars com dígito embutido)
    -> Número da conta: 00587521 (8 chars) -> padded pra 12 no REM
    -> DV da conta: 6

Versão do layout: 103 é o default definido no próprio manual (agosto/2026).
"""

# Beneficiário
CNPJ = "35588873000141"                                # 14 dígitos
RAZAO_SOCIAL = "SOUL INDUSTRIA DE TECIDOS LTDA"

# Endereço do beneficiário (usado no BOLETO PDF)
ENDERECO_LOGRADOURO = "AV RAIMUNDA MARIA ARAGAO, 48 FUNDOS R JOSE A JOAQUIM 202"
ENDERECO_BAIRRO = "BELA VISTA"
ENDERECO_CEP = "55195-515"
ENDERECO_CIDADE = "SANTA CRUZ DO CAPIBARIBE"
ENDERECO_UF = "PE"

# Conta Safra
BANCO = "422"
AGENCIA = "02900"                     # 5 dígitos, sem DV
CONTA_NUMERO = "00587521"             # 8 dígitos (será padded pra 12 no REM)
CONTA_DV = "6"                        # 1 dígito
CONTA_COMPLETA = "005875216"          # usada no código de barras / linha digitável
CARTEIRA = "1"                        # 1 = Cobrança Simples

# Configuração de layout
LAYOUT_VERSAO_ARQUIVO = "103"         # Header Arquivo pos 164-166 (default do manual)
LAYOUT_VERSAO_LOTE = "060"            # Header Lote pos 014-016 (default do manual)

# Cobrança direta (empresa emite e distribui boleto)
CADASTRO_TITULO = "1"                 # 1 = Cobrança Registrada
TIPO_DOCUMENTO = "2"                  # 2 = Escritural
IDENTIFICACAO_BLOQUETO = "2"          # 2 = Cliente Emite Boleto
DISTRIBUICAO_BLOQUETO = "2"           # 2 = Cliente Distribui

# Código do banco na compensação com DV (usado no boleto)
BANCO_DV = "7"                        # 422-7 (Banco Safra S/A)

# Sistema (posição 20 do código de barras Safra)
SISTEMA_SAFRA = "7"

# Frase obrigatória no boleto (praça Safra)
FRASE_INSTRUCOES_SAFRA = (
    "As informacoes contidas neste boleto sao de exclusiva responsabilidade do Beneficiario."
)
