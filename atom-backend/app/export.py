"""Lead batch export: XLSX, CSV and a formatted PDF (Bloco 7)."""
import csv
import io

from fpdf import FPDF
from openpyxl import Workbook

# (chave do lead, cabecalho)
COLS = [
    ("empresa_nome", "Empresa"),
    ("pais", "Pais"),
    ("cidade", "Cidade"),
    ("tipo_negocio", "Tipo"),
    ("site", "Site"),
    ("telefone", "Telefone"),
    ("email", "E-mail"),
    ("whatsapp", "WhatsApp"),
    ("instagram", "Instagram"),
    ("score", "Score"),
]


def build_csv(leads: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for _, h in COLS])
    for ld in leads:
        w.writerow([ld.get(k) for k, _ in COLS])
    return buf.getvalue().encode("utf-8")


def build_xlsx(leads: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append([h for _, h in COLS])
    for ld in leads:
        ws.append([ld.get(k) for k, _ in COLS])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _latin1(s: str) -> str:
    return (s or "").encode("latin-1", "replace").decode("latin-1")


def build_pdf(leads: list[dict], titulo: str) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, _latin1(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, _latin1(f"Total de leads: {len(leads)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    for i, ld in enumerate(leads, 1):
        pdf.set_font("Helvetica", "B", 10)
        empresa = f"{i}. {ld.get('empresa_nome') or '-'}  (score {ld.get('score') or '-'})"
        pdf.cell(0, 6, _latin1(empresa), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=9)
        linha = (
            f"{ld.get('cidade') or '-'} / {ld.get('pais') or '-'} - {ld.get('tipo_negocio') or '-'} - "
            f"tel {ld.get('telefone') or '-'} - {ld.get('email') or '-'}"
        )
        pdf.multi_cell(0, 5, _latin1(linha))
        pdf.ln(1)
    return bytes(pdf.output())
