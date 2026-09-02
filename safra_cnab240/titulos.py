"""
Três títulos fictícios para homologação Safra.

CPFs/CNPJs abaixo têm dígitos verificadores VÁLIDOS (calculados).
CEPs são reais (Santa Cruz do Capibaribe / Recife / São Paulo).

Cenários cobertos pra Mesa avaliar:
  Titulo 1: valor pequeno, sem juros/multa/desconto
  Titulo 2: valor médio, com juros e multa
  Titulo 3: valor grande, com juros, multa e desconto
"""

from datetime import date, timedelta

HOJE = date.today()

TITULOS = [
    {
        "nosso_numero": "000000001",
        "seu_numero": "TESTE00001",
        "especie": "02",                          # 02 = Duplicata Mercantil
        "valor_centavos": 10000,                  # R$ 100,00
        "data_emissao": HOJE,
        "data_vencimento": HOJE + timedelta(days=30),
        "juros_codigo": "1",                      # 1 = valor por dia
        "juros_data": HOJE + timedelta(days=31),  # dia seguinte ao vencimento
        "juros_valor_centavos": 10,               # R$ 0,10/dia (0,10% do valor)
        "multa_codigo": "2",                      # 2 = percentual
        "multa_data": HOJE + timedelta(days=31),
        "multa_percentual": 2.00,                 # 2% de multa
        "desconto_codigo": "0",                   # 0 = sem desconto
        "desconto_data": HOJE + timedelta(days=30),
        "desconto_valor_centavos": 0,
        "protesto_codigo": "3",                   # 3 = não protestar
        "protesto_dias": 0,
        "baixa_codigo": "1",                      # 1 = baixar e devolver
        "baixa_dias": 60,
        "pagador": {
            "tipo_inscricao": "1",                # 1 = CPF
            "cpf_cnpj": "52998224725",            # CPF válido de teste
            "nome": "JOSE DA SILVA TESTE",
            "endereco": "RUA DAS FLORES 100",
            "bairro": "CENTRO",
            "cep_prefixo": "55190",
            "cep_sufixo": "505",
            "cidade": "SANTA CRUZ DO CAPIBAR",    # 15 chars max no campo
            "uf": "PE",
        },
    },
    {
        "nosso_numero": "000000002",
        "seu_numero": "TESTE00002",
        "especie": "02",
        "valor_centavos": 50000,                  # R$ 500,00
        "data_emissao": HOJE,
        "data_vencimento": HOJE + timedelta(days=45),
        "juros_codigo": "1",                      # 1 = valor por dia
        "juros_data": HOJE + timedelta(days=46),
        "juros_valor_centavos": 10,               # R$ 0,10 por dia
        "multa_codigo": "2",                      # 2 = percentual
        "multa_data": HOJE + timedelta(days=46),
        "multa_percentual": 2.00,                 # 2,00%
        "desconto_codigo": "0",
        "desconto_data": HOJE + timedelta(days=45),
        "desconto_valor_centavos": 0,
        "protesto_codigo": "3",
        "protesto_dias": 0,
        "baixa_codigo": "1",
        "baixa_dias": 60,
        "pagador": {
            "tipo_inscricao": "1",                # CPF
            "cpf_cnpj": "31628382821",            # CPF válido
            "nome": "MARIA APARECIDA TESTE",
            "endereco": "AV DEZESSETE DE AGOSTO 500 APT 302",
            "bairro": "CASA FORTE",
            "cep_prefixo": "52061",
            "cep_sufixo": "540",
            "cidade": "RECIFE",
            "uf": "PE",
        },
    },
    {
        "nosso_numero": "000000003",
        "seu_numero": "TESTE00003",
        "especie": "02",
        "valor_centavos": 123456,                 # R$ 1.234,56
        "data_emissao": HOJE,
        "data_vencimento": HOJE + timedelta(days=60),
        "juros_codigo": "1",
        "juros_data": HOJE + timedelta(days=61),
        "juros_valor_centavos": 41,               # R$ 0,41 por dia (~1% ao mês)
        "multa_codigo": "2",
        "multa_data": HOJE + timedelta(days=61),
        "multa_percentual": 2.00,
        "desconto_codigo": "1",                   # 1 = valor fixo até data
        "desconto_data": HOJE + timedelta(days=60),
        "desconto_valor_centavos": 5000,          # R$ 50,00
        "protesto_codigo": "3",
        "protesto_dias": 0,
        "baixa_codigo": "1",
        "baixa_dias": 90,
        "pagador": {
            "tipo_inscricao": "2",                # CNPJ
            "cpf_cnpj": "45283163000167",         # CNPJ válido (fictício)
            "nome": "CONFECCOES TESTE HOMOLOG LTDA",
            "endereco": "RUA DA PAZ 2000 GALPAO 4",
            "bairro": "VILA MADALENA",
            "cep_prefixo": "05436",
            "cep_sufixo": "060",
            "cidade": "SAO PAULO",
            "uf": "SP",
        },
    },
]


def _valida_cpf(cpf):
    if len(cpf) != 11 or not cpf.isdigit():
        return False
    for i in (9, 10):
        s = sum(int(cpf[j]) * ((i + 1) - j) for j in range(i))
        d = (s * 10) % 11
        if d == 10:
            d = 0
        if d != int(cpf[i]):
            return False
    return True


def _valida_cnpj(cnpj):
    if len(cnpj) != 14 or not cnpj.isdigit():
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for i, pesos in enumerate([pesos1, pesos2]):
        s = sum(int(cnpj[j]) * pesos[j] for j in range(len(pesos)))
        r = s % 11
        d = 0 if r < 2 else 11 - r
        if d != int(cnpj[12 + i]):
            return False
    return True


if __name__ == "__main__":
    for t in TITULOS:
        p = t["pagador"]
        doc = p["cpf_cnpj"]
        ok = _valida_cpf(doc) if p["tipo_inscricao"] == "1" else _valida_cnpj(doc)
        print(f"Titulo {t['nosso_numero']}: doc {doc} valido={ok}")
