"""
Testes dos pontos que falham EM SILÊNCIO.

Cada um destes já quebrou de verdade, ou quebraria sem ninguém perceber:
nenhum levanta exceção, todos entregam planilha errada parecendo certa.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnpj import apify, colunas as C, exportar
from cnpj.empresaqui import EmpresAqui, achatar, dv_valido, normalizar


# ─────────────────────────────── dígito verificador

@pytest.mark.parametrize("entrada,esperado", [
    ("21.792.257/0001-01", "21792257000101"),   # pontuado
    ("21792257000101",     "21792257000101"),   # limpo
    (84043009000170,       "84043009000170"),   # Excel virou número
    (4432327000193,        "04432327000193"),   # Excel COMEU o zero da frente
    ("02585301000150",     "02585301000150"),   # zero preservado
])
def test_dv_aceita(entrada, esperado):
    assert normalizar(entrada)[0] == esperado


@pytest.mark.parametrize("ruim", [
    "11.222.333/4444-55",   # DV quebrado
    "11111111111111",       # todos iguais
    "123", "", None, "nao tem",
])
def test_dv_rejeita(ruim):
    assert normalizar(ruim) is None


def test_dv_nao_gasta_requisicao():
    """CNPJ torto é descartado ANTES da chamada — é o que protege a cota."""
    assert not dv_valido("11222333444455")


# ─────────────────────────────── leitura de .xlsx (bug de 2 em 6)

def test_xlsx_le_os_quatro_formatos_do_excel(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Vendedor", "Cod", "CNPJ", "Obs"])
    for l in [("a", 1, "84.683.408/0001-03", "pontuado"),
              ("b", 2, "82640558000104", "texto puro"),
              ("c", 3, 84043009000170, "numero"),
              ("d", 4, 4432327000193, "zero comido"),
              ("e", 5, "84.683.408/0001-03", "DUPLICADO"),
              ("f", 6, "11.222.333/4444-55", "DV quebrado"),
              ("g", 7, "", "vazio")]:
        ws.append(list(l))
    alvo = tmp_path / "p.xlsx"; wb.save(alvo)

    cnpjs, info = exportar.ler_cnpjs(alvo)
    assert len(cnpjs) == 4, "texto no xlsx vem de sharedStrings; sem ler t='s' vira índice"
    assert "04432327000193" in cnpjs, "zero da frente tem de ser restaurado"
    assert info["invalidos_descartados"] == 1
    assert info["coluna_detectada"] == 2, "achar a coluna sozinho, sem mapeamento"


# ─────────────────────────────── casamento por nome

def test_casa_quando_o_nome_bate():
    leads = [{"razao_social": "WEG EQUIPAMENTOS ELETRICOS S/A"}]
    n = apify.casar(leads, [{"title": "WEG Equipamentos Elétricos",
                             "emails": [], "whatsapps": [], "instagrams": []}],
                    apify.de_maps, "title")
    assert n == 1 and leads[0]["match_score"] >= 0.9


def test_maps_entrega_todos_os_valores_nao_so_o_primeiro():
    """
    O código antigo fazia emails[0] e jogava o resto fora: um lugar com
    quatro e-mails entregava um. Lacuna encontrada na auditoria.
    """
    item = {"title": "WEG", "phone": "4732764000",
            "emails": ["a@weg.net", "b@weg.net", "c@weg.net"],
            "whatsapps": ["5547999990000", "5547988880000"],
            "instagrams": ["https://instagram.com/wegoficial", "@weg_br"]}
    d = apify.de_maps(item)
    assert len(d["_email"]) == 3, "todos os e-mails, não só o primeiro"
    assert len(d["_contatos"]) == 3, "telefone + os dois whatsapps"
    assert len(d["_instagram"]) == 2


def test_maps_funde_todos_na_coluna_consolidada():
    lead = achatar(_resposta(enrichment={"email_principal": "a@dohler.com.br"}))[0]
    apify._fundir(lead, apify.de_maps({
        "title": "Dohler", "phone": None, "emails": ["b@dohler.com.br", "c@dohler.com.br"],
        "whatsapps": [], "instagrams": []}), "maps")
    assert len(lead["email"]) == 3, "os dois do Maps entram junto com o que já havia"
    assert lead["fonte_email"][-2:] == ["maps", "maps"]


def test_nao_casa_lazos_com_los_lazos():
    """O erro documentado na spec. Prefere vazio a casar errado."""
    leads = [{"razao_social": "LAZOS COMERCIO LTDA"}]
    n = apify.casar(leads, [{"title": "Frigorífico Los Lazos",
                             "emails": ["x@loslazos.ar"], "whatsapps": [],
                             "instagrams": []}], apify.de_maps, "title")
    assert n == 0 and not leads[0].get("email")


# ─────────────────────────────── consolidação

def _resposta(**extra):
    base = {"cnpj": "84683408000103", "razao": "DOHLER S.A.",
            "ddd_1": "47", "tel_1": "34411666", "email": "a@dohler.com.br",
            "programas_especiais": [], "historicoDividasPorTrimestre": []}
    base.update(extra); return base


def test_fixo_e_whatsapp_na_mesma_coluna():
    """Não há como saber qual número tem WhatsApp. Separar seria inventar."""
    L = achatar(_resposta(enrichment={"telefone_principal": "4733319500",
                                      "whatsapp_principal": "47988616143"}))[0]
    assert set(L["contatos"]) == {"4734411666", "4733319500", "47988616143"}
    assert "whatsapp" not in L, "não existe coluna whatsapp separada"


def test_mesmo_numero_em_formatos_diferentes_conta_uma_vez():
    L = achatar(_resposta(enrichment={"telefone_principal": "(47) 3441-1666",
                                      "telefones_texto": "4734411666"}))[0]
    assert L["contatos"] == ["4734411666"]


def test_campos_texto_separam_por_barra_vertical():
    """Medido na fonte: emails_texto usa ' | ', não vírgula."""
    L = achatar(_resposta(enrichment={
        "emails_texto": "cac@dohler.com.br | sac@dohler.com.br"}))[0]
    assert len(L["email"]) == 3


def test_descarta_email_lixo_da_fonte():
    """exemplo@mail.com e u002f@x.y são lixo que a própria fonte entrega."""
    L = achatar(_resposta(enrichment={
        "emails_texto": "exemplo@mail.com | u002f@dohler.oficial | ok@dohler.com.br"}))[0]
    assert L["email"] == ["a@dohler.com.br", "ok@dohler.com.br"]


def test_socios_nao_contam_dividas():
    """Chaves numéricas misturam sócios e dívidas. Atingia 18% das empresas."""
    L = achatar(_resposta(**{
        "0": {"socios_nome": "A", "socios_qualificacao": "SÓCIO-ADMINISTRADOR"},
        "1": {"socios_nome": "B", "socios_qualificacao": "SÓCIO"},
        "2": {"dividas_numero": "9142302441973", "dividas_valor": "10827200",
              "dividas_receita": "R D Ativa"}}))[0]
    assert L["qtd_socios"] == 2 and L["socios"] == ["A", "B"]
    assert L["qtd_dividas"] == 1 and L["divida_valor_total"] == 10827200.0


def test_todos_os_socios_saem_na_coluna():
    r = _resposta(**{str(i): {"socios_nome": f"S{i}"} for i in range(9)})
    assert len(achatar(r)[0]["socios"]) == 9


# ─────────────────────────────── separador por formato

def test_separador_muda_por_formato():
    v = ["4733319500", "47988616143"]
    assert C.juntar(v, "csv") == "4733319500;47988616143"
    assert C.juntar(v, "xlsx") == "4733319500;47988616143"
    assert C.juntar(v, "pdf") == "4733319500 - 47988616143"


def test_csv_poe_multivalor_entre_aspas(tmp_path):
    """O arquivo já usa ; de coluna; sem aspas o Excel quebra o telefone."""
    L = achatar(_resposta(enrichment={"telefone_principal": "4733319500"}))[0]
    exportar.escrever([L], tmp_path / "x", ("csv",))
    txt = (tmp_path / "x.csv").read_text(encoding="utf-8-sig")
    assert '"4734411666;4733319500"' in txt


# ─────────────────────────────── coluna vazia

def test_coluna_totalmente_vazia_sai():
    L = achatar(_resposta())[0]
    cols, _ = exportar._preparar([L], None, "csv")
    assert "instagram" not in cols


def test_coluna_com_um_unico_valor_permanece():
    """Vazia é vazia de VERDADE, não 'quase vazia'."""
    a = achatar(_resposta(enrichment={"instagram_principal": "@dohler"}))[0]
    b = achatar(_resposta())[0]
    cols, _ = exportar._preparar([a, b], None, "csv")
    assert "instagram" in cols


# ─────────────────────────────── cache

def test_cache_nao_guarda_falha_transitoria(tmp_path, monkeypatch):
    """
    O defeito mais caro: uma oscilação de rede marcava o CNPJ como falho
    PARA SEMPRE e a empresa sumia de toda lista futura.
    """
    api = EmpresAqui(token="x", cache=tmp_path / "c.sqlite")
    for ruim in (0, 429, 500, 502):
        api._guardar("21792257000101", ruim, None)
        assert api._do_cache("21792257000101") is None, f"HTTP {ruim} não pode ficar"
    api._guardar("21792257000101", 200, {"cnpj": "21792257000101"})
    assert api._do_cache("21792257000101")[0] == 200


def test_cache_guarda_nao_encontrado(tmp_path):
    """404 é definitivo: o CNPJ não existe, não adianta perguntar de novo."""
    api = EmpresAqui(token="x", cache=tmp_path / "c.sqlite")
    api._guardar("21792257000101", 404, None)
    assert api._do_cache("21792257000101")[0] == 404


# ─────────────────────────────── teto de CNAE

def test_teto_de_dois_cnaes_no_filtro():
    from cnpj.buscar import CnaesDemais, MAX_CNAES, _onde
    assert MAX_CNAES == 2
    _onde(None, "13,14", "ativa", None, None, False, False)
    with pytest.raises(CnaesDemais):
        _onde(None, "13,14,15", "ativa", None, None, False, False)


def test_planilha_nao_tem_teto_de_cnae():
    """O caminho da planilha não passa pelo filtro: ali CNAE é saída, não critério."""
    import inspect
    fonte = inspect.getsource(exportar.ler_cnpjs)
    assert "cnae" not in fonte and "buscar" not in fonte


# ─────────────────────────────── portão da base

def test_verificar_e_portao_nao_relatorio():
    """
    Num timer às 3h da manhã ninguém lê `print`. Sem código de saída a
    unidade passaria como sucesso com a base errada.
    """
    from cnpj.carregar import verificar
    import inspect
    fonte = inspect.getsource(verificar)
    assert "-> tuple[bool, list[str]]" in inspect.signature(verificar).__str__() \
        or "falhas" in fonte, "verificar precisa devolver o veredito"
    # as checagens que pegam falha silenciosa
    for sinal in ("carga parcial", "deslocadas", "casam com a tabela cnaes"):
        assert sinal in fonte, f"falta a checagem: {sinal}"


def test_conferir_sai_com_erro_quando_reprova(tmp_path, monkeypatch):
    """
    O portão tem de devolver código de saída != 0: num timer às 3h da manhã,
    um `print` não barra nada — a unidade passaria como sucesso com a base
    errada.

    Roda contra base real, montada pelo carregar. A versão antiga usava uma
    conexão falsa, que não tem esquema nenhum — e era o esquema que estava
    errado, então ela não poderia ter pegado o problema.
    """
    from cnpj import carregar

    monkeypatch.setattr(carregar.config, "DADOS", tmp_path)
    db = _base_de_teste(tmp_path)

    monkeypatch.setattr(carregar, "verificar",
                        lambda db=None: (False, ["falha forçada"]))
    with pytest.raises(SystemExit) as e:
        carregar.conferir(db)
    assert e.value.code == 1


# ───────────────────────────── carga: filtro na entrada

def test_carga_barra_ativos_e_orfas(tmp_path, monkeypatch):
    """
    Dois filtros que falham CALADOS se quebrarem:

    1. só situação '02' entra (empresa baixada não é lead);
    2. empresa sem nenhum estabelecimento ativo não entra.

    O segundo já quebrou: o EXISTS sem qualificar a tabela de fora virava
    `x.cnpj_basico = x.cnpj_basico`, sempre verdadeiro, e TODAS as linhas
    passavam. Nenhuma exceção, nenhum aviso — só uma base maior do que devia.
    """
    import duckdb
    from cnpj import carregar

    bruto = tmp_path / "bruto"
    bruto.mkdir()
    monkeypatch.setattr(carregar.config, "DADOS", tmp_path)

    c = duckdb.connect()
    c.execute(f"""COPY (SELECT * FROM (VALUES
      ('11111111','0001','11','SC','8317','1399400','02','1'),
      ('22222222','0001','22','SP','7107','4751201','02','1'),
      ('33333333','0001','33','RJ','6001','1234567','08','1'))
      t(cnpj_basico,cnpj_ordem,cnpj_dv,uf,municipio,cnae_fiscal_principal,
        situacao_cadastral,identificador_matriz_filial))
      TO '{bruto / "estabelecimentos__a.parquet"}' (FORMAT PARQUET)""")
    c.execute(f"""COPY (SELECT * FROM (VALUES
      ('11111111','ALFA LTDA','03'),
      ('22222222','BETA SA','05'),
      ('33333333','MORTA ME','01'))
      t(cnpj_basico,razao_social,porte_empresa))
      TO '{bruto / "empresas__a.parquet"}' (FORMAT PARQUET)""")
    c.close()

    r = carregar.carregar(db=tmp_path / "t.duckdb", bruto=bruto)
    assert r["estabelecimentos"] == 2, "estabelecimento baixado entrou no índice"
    assert r["empresas"] == 2, "empresa sem estabelecimento ativo entrou"

    con = duckdb.connect(str(tmp_path / "t.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM empresas "
                       "WHERE cnpj_basico='33333333'").fetchone()[0] == 0
    con.close()


def test_ajustar_poe_teto_de_memoria():
    """
    Sem teto, o DuckDB assume 80% da RAM física e o kernel mata o processo
    numa máquina de 1 GB — foi exatamente como a carga morreu na VM.
    """
    import duckdb
    from cnpj import carregar

    con = duckdb.connect()
    lim = carregar.ajustar(con)
    assert lim["memory_limit_mb"] >= 256
    assert lim["memory_limit_mb"] <= lim["ram_mb"] * 0.5
    efetivo = con.execute("SELECT current_setting('memory_limit')").fetchone()[0]
    assert efetivo and efetivo != "0 bytes", f"teto não aplicado: {efetivo!r}"
    con.close()


def _base_de_teste(tmp_path):
    """
    Monta uma base pelo MESMO caminho da produção: Parquet → carregar().

    Os outros testes montam tabelas à mão, e foi por isso que ninguém viu
    quando o índice foi enxugado para 8 colunas e a consulta continuou
    pedindo nome_fantasia, bairro, telefone e e-mail. Fixture escrito à mão
    passa sempre; o que precisa passar é o esquema que o carregar constrói.
    """
    import duckdb
    from cnpj import carregar

    bruto = tmp_path / "bruto"
    bruto.mkdir()
    c = duckdb.connect()
    c.execute(f"""COPY (SELECT * FROM (VALUES
      ('11111111','0001','11','SC','8317','1399400','02','1'),
      ('22222222','0002','22','SC','8317','1399400','02','2'),
      ('44444444','0001','44','SP','7107','4751201','02','1'))
      t(cnpj_basico,cnpj_ordem,cnpj_dv,uf,municipio,cnae_fiscal_principal,
        situacao_cadastral,identificador_matriz_filial))
      TO '{bruto / "estabelecimentos__a.parquet"}' (FORMAT PARQUET)""")
    c.execute(f"""COPY (SELECT * FROM (VALUES
      ('11111111','ALFA TECELAGEM LTDA','03'),
      ('22222222','BETA MALHAS SA','05'),
      ('44444444','GAMA COMERCIO ME','01'))
      t(cnpj_basico,razao_social,porte_empresa))
      TO '{bruto / "empresas__a.parquet"}' (FORMAT PARQUET)""")
    c.execute(f"""COPY (SELECT * FROM (VALUES
      ('1399400','Fabricação de outros produtos têxteis'),
      ('4751201','Comércio varejista de informática'))
      t(codigo,descricao))
      TO '{bruto / "cnaes__a.parquet"}' (FORMAT PARQUET)""")
    c.execute(f"""COPY (SELECT * FROM (VALUES
      ('8317','GASPAR'),('7107','SAO PAULO'))
      t(codigo,descricao))
      TO '{bruto / "municipios__a.parquet"}' (FORMAT PARQUET)""")
    c.close()

    db = tmp_path / "base.duckdb"
    carregar.carregar(db=db, bruto=bruto)
    return db


def test_consulta_roda_contra_o_esquema_real(tmp_path, monkeypatch):
    """
    O teste que faltava. Sem ele, a consulta pedia sete colunas que o índice
    não carrega e nada avisava — nem a suíte, nem a carga: só estouraria na
    primeira pesquisa de verdade.
    """
    from cnpj import buscar as mod
    from cnpj import carregar

    monkeypatch.setattr(carregar.config, "DADOS", tmp_path)
    db = _base_de_teste(tmp_path)

    assert mod.contar(db=db, uf="SC", excluir_entregues=False) == 2
    assert mod.contar(db=db, uf="SC", apenas_matriz=True,
                      excluir_entregues=False) == 1
    assert mod.contar(db=db, uf="SC", cnae="13", excluir_entregues=False) == 2
    assert mod.contar(db=db, uf="SC", cnae="4751", excluir_entregues=False) == 0

    linhas = mod.buscar(db=db, uf="SC", excluir_entregues=False)
    assert len(linhas) == 2
    # ordem por CNPJ, estável: a fatia 1 de hoje é a fatia 1 de amanhã
    assert [l["cnpj"] for l in linhas] == ["11111111000111", "22222222000222"]
    assert linhas[0]["razao_social"] == "ALFA TECELAGEM LTDA"
    assert linhas[0]["municipio"] == "GASPAR"
    assert linhas[0]["cnae_descricao"].startswith("Fabricação")
    assert linhas[0]["situacao"] == "ATIVA"
    assert linhas[0]["matriz_filial"] == "MATRIZ"
    assert linhas[0]["porte"] == "PEQUENO PORTE"
    assert linhas[1]["matriz_filial"] == "FILIAL"

    # toda ordenação oferecida tem de rodar: uma que referencie coluna
    # inexistente só aparece quando alguém a usa
    for ordem in mod.ORDENS:
        assert mod.buscar(db=db, uf="SC", ordenar=ordem,
                          excluir_entregues=False)


def test_portao_pega_coluna_que_o_espelho_nao_trouxe(tmp_path, monkeypatch):
    """
    COLUNAS é um pedido, não garantia: se o espelho parar de trazer uma
    coluna, ela simplesmente não carrega e a consulta quebra depois. O portão
    tem de reprovar a base antes de ela entrar em uso.
    """
    import duckdb
    from cnpj import carregar

    monkeypatch.setattr(carregar.config, "DADOS", tmp_path)
    db = _base_de_teste(tmp_path)

    con = duckdb.connect(str(db))
    con.execute("DROP INDEX IF EXISTS ix_empresas_cnpj_basico")
    con.execute("ALTER TABLE empresas DROP COLUMN razao_social")
    con.close()

    ok, falhas = carregar.verificar(db)
    assert not ok
    assert any("razao_social" in f for f in falhas), falhas


# ───────────────────── a ordem das colunas ditada pelo cliente

# Escritos à mão, de propósito. Um teste que leia colunas.py para conferir
# colunas.py não prova nada: ele passaria mesmo se a ordem fosse trocada.
# Esta é a ordem que o cliente ditou, literalmente, e é contra ela que se
# compara.
DOZE_PRIMEIRAS = [
    "CNPJ", "Razão Social", "Nome Fantasia", "Contatos", "E-mail",
    "Instagram", "Site", "Cidade", "Estado", "Sócios", "CNAE", "Atividade",
]


def _leads_de_teste(n=3):
    from cnpj import colunas as c
    return [{col: (["a", "b"] if col in c.MULTIVALOR else f"v{i}")
             for col in c.colunas_de(None)} for i in range(n)]


def test_ordem_das_colunas_no_csv_e_no_xlsx(tmp_path):
    """
    O defeito que isto pega já esteve no código: exportar.py tinha uma segunda
    lista de ordem, de duas versões atrás, pedindo nomes que achatar() não
    produz mais. Nada falhava — as colunas caíam no caminho de "extras",
    ordenado por alfabeto, e a planilha saía com a ordem errada em silêncio.
    """
    from openpyxl import load_workbook

    feitos = exportar.escrever(_leads_de_teste(), tmp_path / "leads",
                               ("csv", "xlsx"))

    cab = feitos["csv"].read_text(encoding="utf-8-sig").splitlines()[0]
    rotulos = [x.strip('"') for x in cab.split(";")]
    assert rotulos[:12] == DOZE_PRIMEIRAS, rotulos[:12]

    # No XLSX tem de ser a mesma ordem: é a mesma planilha, outro formato.
    ws = load_workbook(feitos["xlsx"], read_only=True).active
    cabecalho = [c.value for c in next(ws.rows)]
    assert cabecalho[:12] == DOZE_PRIMEIRAS, cabecalho[:12]


# ───────────────── a lista de 100 é constante, não parâmetro

def test_pedido_de_250_vira_tres_listas_de_cem(tmp_path):
    """
    Toda lista entregue tem no máximo 100 empresas. Era parâmetro do cliente:
    tamanho_fatia=100000 produzia uma fatia única de horas, sem entrega
    parcial, sem retomada barata e sem caber no n8n.
    """
    import json as _json
    from servico.fila import Fila, TAMANHO_LISTA

    assert TAMANHO_LISTA == 100
    f = Fila(tmp_path / "jobs.sqlite")
    r = f.criar([f"{i:014d}" for i in range(250)], filtro="teste")

    assert r["fatias"] == 3
    tamanhos = [len(_json.loads(linha["cnpjs"]))
                for linha in f.db.execute(
                    "SELECT cnpjs FROM fatias WHERE pedido_id=? ORDER BY n",
                    [r["id"]]).fetchall()]
    assert tamanhos == [100, 100, 50], tamanhos

    # e não há como pedir outro tamanho: o parâmetro não existe mais
    import inspect
    assert "tamanho_fatia" not in inspect.signature(f.criar).parameters


def test_api_recusa_entrada_invalida():
    """
    Cada recusa aqui é um defeito que ia aparecer tarde: formato errado
    derrubava a fatia DEPOIS do 202, e CNPJ sujo fazia total_pedido mentir
    sobre o que seria processado.
    """
    import os
    os.environ.setdefault("API_TOKEN", "x")
    from pydantic import ValidationError
    from servico.api import Pedido, TETO_TOTAL

    with pytest.raises(ValidationError):
        Pedido(cnpjs=["84429695000111"], formatos=["docx"])

    with pytest.raises(ValidationError):
        Pedido(cnpjs=["00000000000000", "nada"])        # nenhum válido

    with pytest.raises(ValidationError):
        Pedido(filtro=None, cnpjs=["84429695000111"], total=TETO_TOTAL + 1)

    # CNPJ sujo é limpo e desduplicado na ENTRADA
    p = Pedido(cnpjs=["84.429.695/0001-11", "84429695000111",
                      "86.950.110/0001-30"])
    assert p.cnpjs == ["84429695000111", "86950110000130"]
    assert p.formatos == ["xlsx", "csv"]


# ───────────────── a fila não trava e não mente

def test_pedido_pausado_volta_para_a_fila(tmp_path):
    """
    Token inválido no meio de uma fatia punha o pedido em 'pausado', e
    proxima_fatia só olhava 'pendente' e 'executando'. O pedido congelava
    para sempre, sem erro em lugar nenhum: o cliente esperava uma lista que
    nunca ia sair.
    """
    from servico.fila import Fila

    f = Fila(tmp_path / "jobs.sqlite")
    r = f.criar([f"{i:014d}" for i in range(150)], filtro="teste")

    fatia = f.proxima_fatia()
    assert fatia is not None
    f.devolver_fatia(r["id"], fatia["n"], "token_empresaqui")

    estado = f.db.execute("SELECT status, motivo FROM pedidos WHERE id=?",
                          [r["id"]]).fetchone()
    assert estado["status"] == "pausado"

    # e no ciclo seguinte ela TEM de voltar
    de_novo = f.proxima_fatia()
    assert de_novo is not None, "pedido pausado ficou preso para sempre"
    assert de_novo["n"] == fatia["n"]
    depois = f.db.execute("SELECT status, motivo FROM pedidos WHERE id=?",
                          [r["id"]]).fetchone()
    assert depois["status"] == "executando"
    assert depois["motivo"] is None


def test_fatia_em_erro_faz_pedido_parcial_nao_pronto(tmp_path):
    """
    Nove listas prontas e uma falhada não é pedido pronto. A contagem antiga
    só olhava fatias abertas, então o pedido virava 'pronto' com uma lista
    faltando — lista incompleta entregue como completa.
    """
    from servico.fila import Fila

    f = Fila(tmp_path / "jobs.sqlite")
    r = f.criar([f"{i:014d}" for i in range(250)], filtro="teste")

    for esperado_erro in (False, True, False):
        fatia = f.proxima_fatia()
        f.concluir_fatia(r["id"], fatia["n"], leads=100,
                         erro="estourou" if esperado_erro else None)

    p = f.db.execute("SELECT status, motivo FROM pedidos WHERE id=?",
                     [r["id"]]).fetchone()
    assert p["status"] == "parcial", p["status"]
    assert "1 de 3" in p["motivo"], p["motivo"]


def test_pedido_sem_falha_fica_pronto(tmp_path):
    """O contrário também tem de valer: sem erro nenhum, é pronto."""
    from servico.fila import Fila

    f = Fila(tmp_path / "jobs.sqlite")
    r = f.criar([f"{i:014d}" for i in range(150)], filtro="teste")
    for _ in range(2):
        fatia = f.proxima_fatia()
        f.concluir_fatia(r["id"], fatia["n"], leads=100)

    p = f.db.execute("SELECT status, motivo FROM pedidos WHERE id=?",
                     [r["id"]]).fetchone()
    assert p["status"] == "pronto"
    assert p["motivo"] is None


def test_fatia_orfa_e_retomada_sem_reiniciar_o_worker(tmp_path):
    """
    A recuperação de órfã acontecia UMA vez, na partida do worker. Worker
    vivo mas travado deixava a fatia em 'executando' para sempre.
    """
    from servico.fila import Fila, MINUTOS_ORFA

    f = Fila(tmp_path / "jobs.sqlite")
    r = f.criar([f"{i:014d}" for i in range(100)], filtro="teste")

    fatia = f.proxima_fatia()
    assert f.proxima_fatia() is None, "pegou a mesma fatia duas vezes"

    # envelhece a fatia como se o worker tivesse travado nela
    velho = (__import__("datetime").datetime.now(
        __import__("datetime").timezone.utc)
        - __import__("datetime").timedelta(minutes=MINUTOS_ORFA + 1)
    ).isoformat(timespec="seconds")
    f.db.execute("UPDATE fatias SET iniciada_em=? WHERE pedido_id=? AND n=?",
                 [velho, r["id"], fatia["n"]])
    f.db.commit()

    assert f.proxima_fatia() is not None, "fatia órfã nunca foi retomada"


def test_contagem_junta_so_o_que_o_filtro_usa(tmp_path, monkeypatch):
    """
    Medido na VM de 1 GB, SC + CNAE 13 + matriz: 2,5 s com os dois LEFT JOIN
    contra 2,2 s de cache aquecido, e 0,129 s sem eles. Vinte vezes mais
    rápido, sem índice nenhum — os joins eram puro desperdício para um filtro
    que só olha estabelecimentos.

    O que este teste protege não é a velocidade, é o RESULTADO: juntar menos
    não pode mudar o número.
    """
    from cnpj import buscar as mod
    from cnpj import carregar

    monkeypatch.setattr(carregar.config, "DADOS", tmp_path)
    db = _base_de_teste(tmp_path)

    # o caso comum não junta nada
    assert mod._juntas({"uf": "SC", "cnae": "13", "apenas_matriz": True}) == ""
    # e quem filtra porte ou cidade junta o que precisa
    assert "empresas" in mod._juntas({"porte": "pequeno"})
    assert "municipios" in mod._juntas({"municipio": "GASPAR"})

    # o número não muda por causa disso
    sem = mod.contar(db=db, uf="SC", excluir_entregues=False)
    com = mod.contar(db=db, uf="SC", municipio="GASPAR",
                     excluir_entregues=False)
    assert sem == 2
    assert com == 2, "a junta mudou o resultado"

    # e o filtro por porte continua funcionando, agora com a junta certa
    assert mod.contar(db=db, uf="SC", porte="pequeno",
                      excluir_entregues=False) == 1
