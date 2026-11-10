"""Deterministic mocks for E1 (descoberta), E2 (enriquecimento), E5 (limpeza).

They let the full journey run and be tested without external keys. Costs are
plausible so the guardrail logic is exercised. Real clients replace these in
Bloco 5 behind the same contracts (app/providers/base.py).
"""
from app.providers.base import EmpresaAlvo, LeadLimpo


class MockDiscovery:
    def descobrir(self, produto, mercado, perfil, n):
        empresas = [
            EmpresaAlvo(
                empresa=f"{mercado} Importadora {i:03d}",
                cidade=f"Cidade {i % 7}",
                site=f"https://importadora{i:03d}.example.com",
            )
            for i in range(1, n + 1)
        ]
        return empresas, round(0.003 * n, 4)


class MockEnrichment:
    def enriquecer(self, empresas, pais):
        brutos = []
        for i, e in enumerate(empresas):
            brutos.append(
                {
                    "title": e.empresa,
                    "cidade": e.cidade,
                    "website": e.site,
                    "phone": f"+1-555-{1000 + i:04d}",
                    "email": f"contato@importadora{i + 1:03d}.example.com",
                    "whatsapp": f"+595-9{i:08d}" if pais.lower() != "eua" else None,
                    "instagram": f"https://instagram.com/importadora{i + 1:03d}",
                    "categoryName": "Wholesaler" if i % 2 == 0 else "Distributor",
                    "pais": pais,
                }
            )
        return brutos, round(0.002 * len(empresas), 4)


class MockCleaner:
    def limpar(self, brutos, produto, perfil, alvo):
        vistos: set[str] = set()
        leads: list[LeadLimpo] = []
        for b in brutos:
            nome = b.get("title")
            if not nome or nome in vistos:
                continue
            vistos.add(nome)
            leads.append(
                LeadLimpo(
                    empresa_nome=nome,
                    pais=b.get("pais"),
                    cidade=b.get("cidade"),
                    tipo_negocio=b.get("categoryName"),
                    site=b.get("website"),
                    telefone=b.get("phone"),
                    email=b.get("email"),
                    whatsapp=b.get("whatsapp"),
                    instagram=b.get("instagram"),
                    score=round(70 + (len(leads) % 30), 1),
                    racional=f"Aderente ao perfil ({perfil or 'importador'}) para {produto or 'produto'}.",
                    fontes={"telefone": "maps", "email": "maps", "instagram": "maps"},
                )
            )
            if len(leads) >= alvo:
                break
        return leads, 0.25
