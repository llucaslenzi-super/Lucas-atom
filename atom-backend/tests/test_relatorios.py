"""Bloco 3: leitura dos 2 modelos de relatorio (Plano de Exportacao / Mapa de Valor)."""
import io

from fpdf import FPDF

from app.providers.report_parser import HeuristicReportParser

SURF = (
    "Roteiro - Topicos obrigatorios\n"
    "Indicacao do produto a ser exportado (aquele trabalhado durante o PEIEX):\n"
    "Prancha de surf mecanica (simulador de surf) de alta tecnologia.\n"
    "A) Indique o SH6 (ou NCM) do produto. SH6/NCM: 9506.91.00\n"
    "B) Mercado selecionado: O mercado de maior potencial imediato e EUA.\n"
)
SOUS = (
    "Indicacao do produto a ser exportado (aquele trabalhado durante PEIEX): "
    "Kit de calcinhas de algodao\n"
    "A) SH6/NCM: 6108.21.00\n"
    "B) Mercado selecionado: Paraguai\n"
)
RIGBIE = (
    "ORIENTACOES PARA PREENCHIMENTO - MAPA DE VALOR\n"
    "A) Descreva brevemente o servico a ser exportado: software de gestao da CIPA.\n"
    "H) Especifique o NBS. NBS 1.1103.22.00.\n"
    "Uma vez que o Mexico sera tratado como mercado prioritario neste Mapa de Valor.\n"
)
TECHFRIG = (
    "MAPA DE VALOR\n"
    "A) Descreva brevemente o servico a ser exportado: maquinas para frigorificos.\n"
    "H) Especifique o NBS do servico. A classificacao fiscal reflete o CNAE 28.62-3-00.\n"
    "G) A Techfrig direciona esforcos para mercados com industria de proteina animal.\n"
)


def test_parse_produto_surf():
    r = HeuristicReportParser().parse(SURF)
    assert r.tipo == "produto"
    assert r.codigo_fiscal == "9506.91.00"
    assert r.mercado_sugerido == "EUA"
    assert "surf" in (r.produto_descricao or "").lower()


def test_parse_produto_sous():
    r = HeuristicReportParser().parse(SOUS)
    assert r.tipo == "produto"
    assert r.codigo_fiscal == "6108.21.00"
    assert r.mercado_sugerido == "Paraguai"
    assert "calcinha" in (r.produto_descricao or "").lower()


def test_parse_servico_rigbie():
    r = HeuristicReportParser().parse(RIGBIE)
    assert r.tipo == "servico"
    assert r.codigo_fiscal == "1.1103.22.00"
    assert r.mercado_sugerido == "México"


def test_parse_servico_techfrig_sem_pais_unico():
    r = HeuristicReportParser().parse(TECHFRIG)
    assert r.tipo == "servico"
    assert r.codigo_fiscal == "28.62-3-00"  # CNAE fallback (sem NBS)
    assert r.mercado_sugerido is None  # relatorio nao crava um pais


def _pdf_bytes(texto: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, texto)
    return bytes(pdf.output())


def test_upload_endpoint_extracts_and_persists(client, tenant_factory):
    t = tenant_factory("Rel")
    files = {"file": ("surf.pdf", io.BytesIO(_pdf_bytes(SURF)), "application/pdf")}
    r = client.post(
        "/v1/relatorios", headers={"Authorization": f"Bearer {t['token']}"}, files=files
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tipo"] == "produto"
    assert body["codigo_fiscal"] == "9506.91.00"
    assert body["mercado_sugerido"] == "EUA"
    assert body["id"]
