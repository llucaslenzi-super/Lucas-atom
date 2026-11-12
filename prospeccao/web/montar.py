#!/usr/bin/env python3
"""
Monta a página única: estilo.css e o wordmark real da Missner entram
dentro do app.html.

O wordmark é máscara, não imagem colorida: a cor sai de currentColor, então
o mesmo arquivo serve navy sobre claro e branco sobre navy. É a marca de
verdade, extraída do arquivo da Missner — não uma fonte parecida.
"""
import base64
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def montar() -> str:
    html = (AQUI / "app.html").read_text(encoding="utf-8")
    css = (AQUI / "estilo.css").read_text(encoding="utf-8")
    png = (AQUI / "marca.png").read_bytes()
    marca = "data:image/png;base64," + base64.b64encode(png).decode()

    if "/*{{ESTILO}}*/" not in html:
        raise SystemExit("app.html perdeu o marcador /*{{ESTILO}}*/")
    css = css.replace(":root {", ":root {\n  --marca: url('%s');" % marca, 1)
    if "--marca:" not in css:
        raise SystemExit("estilo.css perdeu o :root — a marca não entrou")
    return html.replace("/*{{ESTILO}}*/", css)


if __name__ == "__main__":
    saida = montar()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(saida, encoding="utf-8")
    else:
        sys.stdout.write(saida)
