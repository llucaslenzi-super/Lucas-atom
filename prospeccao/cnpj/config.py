"""Configuração do pipeline de prospecção."""
import os
from pathlib import Path

# Estados em escopo. Carregar só estes mantém a base pequena e a consulta rápida.
UFS = ["SC", "SP", "RS", "PR", "MG", "RJ", "MT"]

RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("CNPJ_DADOS", RAIZ / "dados"))
BRUTO = DADOS / "bruto"          # zips/parquet baixados
DB = DADOS / "cnpj.duckdb"       # base consultável
CACHE = DADOS / "empresaqui.sqlite"
SAIDA = Path(os.environ.get("CNPJ_SAIDA", RAIZ / "saida"))

# Token do EmpresAqui — SEMPRE por variável de ambiente, nunca no código.
#   export EMPRESAQUI_TOKEN="..."
TOKEN = os.environ.get("EMPRESAQUI_TOKEN", "").strip()

# A doc do EmpresAqui se contradiz: o topo mostra token no path, o corpo mostra
# query string. O de query string é o autoritativo (tem OpenAPI e códigos de erro).
# Se o outro estiver vivo, trocar aqui.
ENDPOINT = "https://www.empresaqui.com.br/acesso/RetornoJson.php"
ENDPOINT_PATH = "https://www.empresaqui.com.br/api/{token}/{cnpj}"

# Limite publicado: 1 requisição por segundo por token. Folga de 5% pra não raspar.
INTERVALO_SEG = 1.05

# Fontes da base da Receita.
# O host oficial reseta conexão com frequência; o espelho serve Parquet via Hugging Face.
FONTE_OFICIAL = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/"
FONTE_ESPELHO_HF = "cnpjaberto/cnpj-dados-receita-brasil-2026-10"

# Decodificadores da API EmpresAqui (1 dígito, diferente dos arquivos da Receita que usam 2).
SITUACAO = {"1": "NULA", "2": "ATIVA", "3": "SUSPENSA", "4": "INAPTA", "8": "BAIXADA"}
PORTE_API = {"0": "NAO INFORMADO", "1": "MICROEMPRESA",
             "3": "PEQUENO PORTE", "5": "MEDIO/GRANDE PORTE"}

# Criar na importação é conveniente no uso local, mas sob systemd o
# repositório é montado somente-leitura (ProtectSystem=strict) e um mkdir
# ali derruba o processo antes de ele começar. Em serviço, quem cria os
# diretórios é o instalador; aqui a falha é ignorada de propósito.
for _d in (DADOS, BRUTO, SAIDA):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
