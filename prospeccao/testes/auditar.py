"""
Auditoria da suíte: quebra cada correção de propósito e exige que os testes
peguem. Teste que não falha quando o bug volta não está testando nada.

    python3 testes/auditar.py
"""
import pathlib
import shutil
import subprocess
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Cada entrada reverte UMA correção ao estado defeituoso de antes.
SABOTAGENS = [
    ("cache guarda falha transitória", "empresaqui",
     "        if http not in (200, 404):\n            return\n", ""),
    ("sócios contam dívidas", "empresaqui",
     'socios = [d for d in numericas if d.get("socios_nome")]',
     'socios = list(numericas)'),
    ("campos *_texto separam por vírgula", "empresaqui",
     r'_SEPARADORES = re.compile(r"[|,;\n]")', r'_SEPARADORES = re.compile(r"[,]")'),
    ("e-mail lixo da fonte passa", "empresaqui",
     "        emails = _emails_validos([e.lower() for e in _lista(",
     "        emails = ([e.lower() for e in _lista("),
    ("Maps guarda só o primeiro item", "apify",
     '"_email": list(item.get("emails") or []),',
     '"_email": (item.get("emails") or [])[:1],'),
    ("casamento aceita nome fraco", "apify",
     'chave_lead="razao_social", minimo=0.62', 'chave_lead="razao_social", minimo=0.20'),
    ("coluna vazia testa chave, não valor", "exportar",
     '    def tem_valor(c):\n        return any(l.get(c) not in (None, "", [], {}, False) or',
     "    def tem_valor(c):\n        return any(c in l or"),
    ("separador do PDF igual ao do CSV", "colunas",
     'SEPARADOR = {"csv": ";", "xlsx": ";", "pdf": " - "}',
     'SEPARADOR = {"csv": ";", "xlsx": ";", "pdf": ";"}'),
    ("teto de CNAE removido", "buscar",
     "        if len(cnae) > MAX_CNAES:", "        if False:"),
    # A que escapou de verdade: a consulta pedindo coluna que o indice enxuto
    # nao carrega. Passou pela suite inteira porque os fixtures eram escritos
    # a mao, com todas as colunas.
    ("consulta pede coluna que o índice não tem", "buscar",
     "  em.razao_social,\n  CASE e.situacao_cadastral",
     "  em.razao_social,\n  e.nome_fantasia,\n  CASE e.situacao_cadastral"),
    ("ordenação referencia coluna inexistente", "buscar",
     'ORDENS = {"cnpj": "cnpj"}',
     'ORDENS = {"cnpj": "cnpj", "contato": "e.email DESC"}'),
    ("portão não confere as colunas da base", "carregar",
     "            faltando = [c for c in queridas if c not in tem]",
     "            faltando = []"),
    # A ordem que o cliente ditou. Trocar as duas primeiras tem de reprovar.
    ("ordem das colunas trocada", "colunas",
     '"cnpj", "razao_social", "nome_fantasia", "contatos", "email",',
     '"razao_social", "cnpj", "nome_fantasia", "contatos", "email",'),
]

# Sabotagens fora de cnpj/: a pasta é escolhida pelo prefixo do módulo.
SABOTAGENS += [
    ("lista deixa de ter 100 no máximo", "servico/fila",
     "TAMANHO_LISTA = 100", "TAMANHO_LISTA = 100000"),
    ("pedido pausado não volta para a fila", "servico/fila",
     "AND p.status IN ('pendente','executando','pausado')",
     "AND p.status IN ('pendente','executando')"),
    ("fatia em erro não impede pedido pronto", "servico/fila",
     'final = "parcial" if resto["falhas"] else "pronto"',
     'final = "pronto"'),
    ("fatia órfã nunca é retomada", "servico/fila",
     "OR (f.status='executando' AND f.iniciada_em < ?))",
     "OR (f.status='executando' AND 1=0))"),
]


def _limpar_bytecode():
    """Sem isso a auditoria se contamina: o .pyc da rodada anterior sobrevive."""
    for d in RAIZ.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(RAIZ / ".pytest_cache", ignore_errors=True)


def _suite_falha() -> bool:
    _limpar_bytecode()
    r = subprocess.run([sys.executable, "-m", "pytest", "testes/", "-q", "--no-header",
                        "-p", "no:cacheprovider"], cwd=RAIZ, capture_output=True, text=True)
    return r.returncode != 0


def main() -> int:
    arquivos = {m: (RAIZ / f"{m}.py" if "/" in m else RAIZ / "cnpj" / f"{m}.py")
                for _, m, _, _ in SABOTAGENS}
    original = {m: p.read_text() for m, p in arquivos.items()}

    if _suite_falha():
        print("A suíte já falha com o código íntegro. Corrija antes de auditar.")
        return 2

    print(f"{'SABOTAGEM':44} VEREDITO")
    print("-" * 64)
    pegos = []
    try:
        for nome, mod, alvo, troca in SABOTAGENS:
            s = original[mod]
            if alvo not in s:
                print(f"{nome:44} ALVO SUMIU — auditoria desatualizada")
                continue
            arquivos[mod].write_text(s.replace(alvo, troca, 1))
            ok = _suite_falha()
            arquivos[mod].write_text(s)
            pegos.append(ok)
            print(f"{nome:44} {'pegou' if ok else '*** PASSOU DESPERCEBIDO ***'}")
    finally:
        for m, p in arquivos.items():
            p.write_text(original[m])
        _limpar_bytecode()

    print("-" * 64)
    print(f"  {sum(pegos)}/{len(pegos)} sabotagens detectadas")
    assert not _suite_falha(), "código não restaurou"
    print("  código restaurado e suíte verde")
    return 0 if all(pegos) else 1


if __name__ == "__main__":
    sys.exit(main())
