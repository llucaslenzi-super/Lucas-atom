"""
A tabela de saída: ordem, rótulos e blocos.

A ordem das 12 primeiras foi definida pelo cliente, literalmente. Da 13 em
diante é organização por afinidade.

As 78 colunas saíram de 61 respostas reais da API, não de leitura de
documentação — foi assim que apareceram os 8 campos de dívida ativa que a
doc não menciona.

REGRA DO MULTIVALOR: coluna listada em MULTIVALOR guarda uma LISTA em
memória. O separador é decidido na exportação, nunca aqui:
    CSV e XLSX → ";"      PDF → " - "
"""

# ─────────────────────────────────────────── blocos, na ordem de saída

BLOCOS = {
    "nucleo": [
        "cnpj", "razao_social", "nome_fantasia", "contatos", "email",
        "instagram", "site", "cidade", "estado", "socios",
        "cnae_codigo", "cnae_descricao",
    ],
    "redes": ["linkedin", "facebook", "google_maps"],
    "empresa": [
        "porte", "situacao", "data_situacao", "data_abertura", "idade_anos",
        "natureza_juridica", "capital_social", "faturamento",
        "quadro_funcionarios", "matriz_filial", "cnpj_base",
    ],
    "fiscal": [
        "regime_tributario", "historico_regime_por_ano",
        "opcao_simples", "data_simples", "data_exclusao_simples",
        "opcao_mei", "data_mei", "data_exclusao_mei",
    ],
    "atividade": ["cnae_secundario_codigos", "cnae_secundario_descricoes"],
    "programas": [
        "programas_especiais", "importa_exporta",
        "empresa_cidada", "pat", "recuperacao_judicial",
    ],
    "endereco": [
        "logradouro", "numero", "complemento", "bairro", "cep",
        "municipio_codigo", "pais",
    ],
    "socios": [
        "socios_qualificacoes", "socios_entrada", "socios_cpf", "qtd_socios",
    ],
    "dividas": [
        "qtd_dividas", "divida_valor_total", "dividas_valores",
        "dividas_receitas", "dividas_situacoes", "dividas_inscricoes",
        "dividas_datas", "dividas_numeros",
        "qtd_trimestres_com_divida", "historico_dividas", "situacao_alerta",
    ],
    "scraping": [
        "maps_titulo", "maps_categoria", "maps_endereco",
        "instagram_bio", "instagram_seguidores", "instagram_categoria",
        "match_score",
    ],
    "procedencia": [
        "fonte_contatos", "fonte_email", "fonte_instagram", "fonte_site",
        "enrichment_vazio", "base_competencia", "extraido_em", "lote_id",
    ],
}

# O núcleo é obrigatório: sem cnpj e contatos a planilha não serve para nada.
BLOCO_OBRIGATORIO = "nucleo"

COLUNAS = [c for cols in BLOCOS.values() for c in cols]

# ─────────────────────────────────────────── multivalor

# Toda coluna aqui guarda LISTA. O separador é decidido na exportação.
MULTIVALOR = {
    "contatos", "email", "instagram", "site", "socios",
    "linkedin", "facebook", "google_maps",
    "socios_qualificacoes", "socios_entrada", "socios_cpf",
    "dividas_valores", "dividas_receitas", "dividas_situacoes",
    "dividas_inscricoes", "dividas_datas", "dividas_numeros",
    "historico_dividas", "historico_regime_por_ano", "programas_especiais",
    "cnae_secundario_codigos", "cnae_secundario_descricoes",
    "fonte_contatos", "fonte_email", "fonte_instagram", "fonte_site",
}

SEPARADOR = {"csv": ";", "xlsx": ";", "pdf": " - "}

# Colunas que o Excel precisa tratar como TEXTO, senão come o zero da frente.
TEXTO_FORCADO = {"cnpj", "cnpj_base", "cep", "contatos", "socios_cpf",
                 "municipio_codigo", "cnae_codigo"}

# ─────────────────────────────────────────── rótulos

ROTULOS = {
    "cnpj": "CNPJ", "razao_social": "Razão Social", "nome_fantasia": "Nome Fantasia",
    "contatos": "Contatos", "email": "E-mail", "instagram": "Instagram",
    "site": "Site", "cidade": "Cidade", "estado": "Estado", "socios": "Sócios",
    "cnae_codigo": "CNAE", "cnae_descricao": "Atividade",
    "linkedin": "LinkedIn", "facebook": "Facebook", "google_maps": "Google Maps",
    "porte": "Porte", "situacao": "Situação", "data_situacao": "Data da Situação",
    "data_abertura": "Abertura", "idade_anos": "Idade (anos)",
    "natureza_juridica": "Natureza Jurídica", "capital_social": "Capital Social",
    "faturamento": "Faturamento", "quadro_funcionarios": "Funcionários",
    "matriz_filial": "Matriz/Filial", "cnpj_base": "CNPJ Base",
    "regime_tributario": "Regime Tributário",
    "historico_regime_por_ano": "Regime por Ano",
    "opcao_simples": "Simples", "data_simples": "Simples Desde",
    "data_exclusao_simples": "Simples Até", "opcao_mei": "MEI",
    "data_mei": "MEI Desde", "data_exclusao_mei": "MEI Até",
    "cnae_secundario_codigos": "CNAEs Secundários",
    "cnae_secundario_descricoes": "Atividades Secundárias",
    "programas_especiais": "Programas Especiais",
    "importa_exporta": "Importa/Exporta", "empresa_cidada": "Empresa Cidadã",
    "pat": "PAT", "recuperacao_judicial": "Recuperação Judicial",
    "logradouro": "Logradouro", "numero": "Número", "complemento": "Complemento",
    "bairro": "Bairro", "cep": "CEP", "municipio_codigo": "Cód. Município",
    "pais": "País",
    "socios_qualificacoes": "Qualificação dos Sócios",
    "socios_entrada": "Entrada dos Sócios", "socios_cpf": "CPF dos Sócios",
    "qtd_socios": "Qtd. Sócios",
    "qtd_dividas": "Qtd. Dívidas", "divida_valor_total": "Dívida Total (R$)",
    "dividas_valores": "Valores das Dívidas", "dividas_receitas": "Órgãos",
    "dividas_situacoes": "Situação das Dívidas",
    "dividas_inscricoes": "Inscrições", "dividas_datas": "Datas das Dívidas",
    "dividas_numeros": "Nº das Inscrições",
    "qtd_trimestres_com_divida": "Trimestres com Dívida",
    "historico_dividas": "Histórico (26 trimestres)",
    "situacao_alerta": "Alerta",
    "maps_titulo": "Nome no Maps", "maps_categoria": "Categoria no Maps",
    "maps_endereco": "Endereço no Maps", "instagram_bio": "Bio do Instagram",
    "instagram_seguidores": "Seguidores", "instagram_categoria": "Categoria no IG",
    "match_score": "Confiança do Match",
    "fonte_contatos": "Origem dos Contatos", "fonte_email": "Origem do E-mail",
    "fonte_instagram": "Origem do Instagram", "fonte_site": "Origem do Site",
    "enrichment_vazio": "Sem Enriquecimento",
    "base_competencia": "Competência da Base", "extraido_em": "Extraído em",
    "lote_id": "Lote",
}


def colunas_de(blocos=None) -> list[str]:
    """Colunas na ordem, filtradas por bloco. O núcleo entra sempre."""
    if not blocos:
        return list(COLUNAS)
    pedidos = {b.strip().lower() for b in
               (blocos.split(",") if isinstance(blocos, str) else blocos)}
    pedidos.add(BLOCO_OBRIGATORIO)
    return [c for b, cols in BLOCOS.items() if b in pedidos for c in cols]


def rotulo(coluna: str) -> str:
    return ROTULOS.get(coluna, coluna.replace("_", " ").title())


def juntar(valor, formato="csv"):
    """Lista → string, com o separador do formato. Vazio vira string vazia."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SIM" if valor else "NÃO"
    if not isinstance(valor, (list, tuple, set)):
        return str(valor)
    itens = [str(v).strip() for v in valor if v not in (None, "", [])]
    return SEPARADOR.get(formato, ";").join(dict.fromkeys(itens))
