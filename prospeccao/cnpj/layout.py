"""
Layout dos arquivos de Dados Abertos CNPJ da Receita Federal.

┌─────────────────────────────────────────────────────────────────────┐
│  ATENÇÃO — CONFERIR ANTES DE CONFIAR                                │
│                                                                     │
│  Os CSVs da Receita vêm SEM CABEÇALHO. A ordem das colunas abaixo   │
│  veio da documentação de layout, NÃO de inspeção dos arquivos.      │
│                                                                     │
│  Antes de usar em produção, rode:                                   │
│      python -m cnpj conferir                                        │
│  e compare com LAYOUT_DADOS_ABERTOS_CNPJ.pdf.                       │
│                                                                     │
│  Se a ordem estiver errada, os dados carregam sem erro nenhum e     │
│  ficam silenciosamente trocados. É o bug mais caro possível aqui.   │
└─────────────────────────────────────────────────────────────────────┘

Formato dos arquivos: CSV, separador ';', aspas '"', encoding latin-1 (ISO-8859-1).
"""

ENCODING = "latin-1"
DELIM = ";"

# ---------------------------------------------------------------- ESTABELECIMENTOS
# O coração do filtro: UF, município, CNAE, situação cadastral, telefone, email.
# Um registro por estabelecimento (matriz e cada filial).
ESTABELECIMENTOS = {
    "cnpj_basico": "VARCHAR",               # 8 dígitos — chave de junção com empresas
    "cnpj_ordem": "VARCHAR",                # 4 dígitos — 0001 = matriz
    "cnpj_dv": "VARCHAR",                   # 2 dígitos verificadores
    "matriz_filial": "VARCHAR",             # 1=MATRIZ  2=FILIAL
    "nome_fantasia": "VARCHAR",
    "situacao_cadastral": "VARCHAR",        # 01 NULA 02 ATIVA 03 SUSPENSA 04 INAPTA 08 BAIXADA
    "data_situacao_cadastral": "VARCHAR",   # AAAAMMDD
    "motivo_situacao_cadastral": "VARCHAR",
    "nome_cidade_exterior": "VARCHAR",
    "pais": "VARCHAR",
    "data_inicio_atividade": "VARCHAR",     # AAAAMMDD — data de abertura
    "cnae_principal": "VARCHAR",            # 7 dígitos, sem pontuação
    "cnae_secundario": "VARCHAR",           # CSV de 7 dígitos — NÃO é array
    "tipo_logradouro": "VARCHAR",
    "logradouro": "VARCHAR",
    "numero": "VARCHAR",
    "complemento": "VARCHAR",
    "bairro": "VARCHAR",
    "cep": "VARCHAR",
    "uf": "VARCHAR",                        # <<< filtro principal
    "municipio": "VARCHAR",                 # CÓDIGO DA RECEITA, não IBGE — join com municipios
    "ddd_1": "VARCHAR",
    "telefone_1": "VARCHAR",
    "ddd_2": "VARCHAR",
    "telefone_2": "VARCHAR",
    "ddd_fax": "VARCHAR",
    "fax": "VARCHAR",
    "email": "VARCHAR",
    "situacao_especial": "VARCHAR",
    "data_situacao_especial": "VARCHAR",
}

# ---------------------------------------------------------------- EMPRESAS
# Um registro por cnpj_basico (a empresa, não o estabelecimento).
EMPRESAS = {
    "cnpj_basico": "VARCHAR",
    "razao_social": "VARCHAR",
    "natureza_juridica": "VARCHAR",
    "qualificacao_responsavel": "VARCHAR",
    "capital_social": "VARCHAR",            # decimal com VÍRGULA — converter na carga
    "porte": "VARCHAR",                     # 00 NÃO INFORMADO 01 MICRO 03 PEQUENO 05 DEMAIS
    "ente_federativo": "VARCHAR",
}

# ---------------------------------------------------------------- SOCIOS
SOCIOS = {
    "cnpj_basico": "VARCHAR",
    "identificador_socio": "VARCHAR",       # 1 PJ  2 PF  3 ESTRANGEIRO
    "nome_socio": "VARCHAR",
    "cnpj_cpf_socio": "VARCHAR",            # CPF mascarado
    "qualificacao_socio": "VARCHAR",        # join com qualificacoes — 49 = SÓCIO-ADMINISTRADOR
    "data_entrada": "VARCHAR",
    "pais": "VARCHAR",
    "representante_legal": "VARCHAR",
    "nome_representante": "VARCHAR",
    "qualificacao_representante": "VARCHAR",
    "faixa_etaria": "VARCHAR",
}

# ---------------------------------------------------------------- SIMPLES
SIMPLES = {
    "cnpj_basico": "VARCHAR",
    "opcao_simples": "VARCHAR",             # S / N
    "data_opcao_simples": "VARCHAR",
    "data_exclusao_simples": "VARCHAR",
    "opcao_mei": "VARCHAR",                 # S / N
    "data_opcao_mei": "VARCHAR",
    "data_exclusao_mei": "VARCHAR",
}

# ---------------------------------------------------------------- TABELAS DE DOMÍNIO
DOMINIO = {"codigo": "VARCHAR", "descricao": "VARCHAR"}
CNAES = MUNICIPIOS = NATUREZAS = QUALIFICACOES = PAISES = MOTIVOS = DOMINIO

# ---------------------------------------------------------------- MAPA ARQUIVO → SCHEMA
# A chave é o sufixo que a Receita usa no nome do arquivo extraído.
ARQUIVOS = {
    "ESTABELE":   ("estabelecimentos", ESTABELECIMENTOS),
    "EMPRECSV":   ("empresas",         EMPRESAS),
    "SOCIOCSV":   ("socios",           SOCIOS),
    "SIMPLES":    ("simples",          SIMPLES),
    "CNAECSV":    ("cnaes",            CNAES),
    "MUNICCSV":   ("municipios",       MUNICIPIOS),
    "NATJUCSV":   ("naturezas",        NATUREZAS),
    "QUALSCSV":   ("qualificacoes",    QUALIFICACOES),
    "PAISCSV":    ("paises",           PAISES),
    "MOTICSV":    ("motivos",          MOTIVOS),
}

# ---------------------------------------------------------------- DECODIFICADORES
SITUACAO_CADASTRAL = {
    "01": "NULA", "02": "ATIVA", "03": "SUSPENSA", "04": "INAPTA", "08": "BAIXADA",
}
PORTE = {
    "00": "NAO INFORMADO", "01": "MICROEMPRESA",
    "03": "PEQUENO PORTE", "05": "DEMAIS (MEDIO/GRANDE)",
}
MATRIZ_FILIAL = {"1": "MATRIZ", "2": "FILIAL"}

# Qualificações de sócio que representam decisor real.
# 49 = SÓCIO-ADMINISTRADOR · 05 = ADMINISTRADOR · 16 = PRESIDENTE · 10 = DIRETOR
QUALIFICACAO_DECISOR = {"49", "05", "16", "10"}

# Divisões CNAE que são indústria (Seções B e C).
CNAE_INDUSTRIA = [f"{d:02d}" for d in range(5, 34)]   # 05..33
