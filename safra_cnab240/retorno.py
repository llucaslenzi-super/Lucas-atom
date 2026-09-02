"""
Parser de arquivo RETORNO CNAB 240 - Safra layout 103 (FEBRABAN).

Estrutura: HA(0) + HL(1) + N*(T+U) + TL(5) + TA(9).
Segmento W (dados PIX/QRCode) é ignorado.

Uso:
    from retorno import parse_retorno, classificar_evento
    r = parse_retorno(open("arq.RET").read())
    for e in r["eventos"]:
        c = classificar_evento(e)
        print(c["nosso_numero"], c["status"], c["valor_pago_centavos"])
"""

from datetime import datetime


OCORRENCIAS = {
    "02": "Entrada confirmada",
    "03": "Entrada rejeitada",
    "04": "Transferência de carteira - Entrada",
    "05": "Transferência de carteira - Baixa",
    "06": "Liquidação normal",
    "07": "Confirmação alteração",
    "08": "Liquidação em cartório",
    "09": "Baixa",
    "10": "Baixa por decurso de prazo",
    "11": "Títulos em ser",
    "12": "Confirmação abatimento",
    "13": "Cancelamento abatimento",
    "14": "Confirmação alteração vencimento",
    "17": "Liquidação após baixa",
    "19": "Confirmação pedido protesto",
    "20": "Confirmação sustação protesto",
    "23": "Remessa a cartório",
    "24": "Retirada de cartório",
    "25": "Protestado e baixado",
    "26": "Instrução rejeitada",
    "27": "Confirmação alteração outros dados",
    "28": "Débito tarifas/custas",
    "29": "Ocorrências do pagador",
    "30": "Alteração dados rejeitada",
    "33": "Confirmação negativação",
    "34": "Confirmação exclusão negativação",
    "40": "Estorno de pagamento",
    "45": "Título pago com cheque devolvido",
    "46": "Título pago com cheque compensado",
    "51": "DDA reconhecido",
    "52": "DDA não reconhecido",
}


MOTIVOS = {
    "00": "OK",
    "01": "Código banco inválido",
    "02": "Código registro inválido",
    "03": "Código ocorrência inválido",
    "04": "Código carteira inválido",
    "05": "Ag/conta inválido",
    "06": "Nosso número inválido",
    "07": "Nosso número duplicado",
    "08": "Tamanho NN inválido",
    "09": "Ag/conta inexistente",
    "10": "Título já existe",
    "11": "Título não existe",
    "12": "Beneficiário não permite baixa",
    "13": "Título com abatimento",
    "14": "Título com desconto",
    "15": "Título já baixado/liquidado",
    "16": "Forma cobrança diferente",
    "17": "Título já em cartório",
    "18": "Data vencimento inválida",
    "19": "Vencimento anterior à emissão",
    "20": "Data emissão inválida",
    "21": "Valor título inválido",
    "22": "Espécie inválida",
    "23": "Espécie não permite emissão",
    "24": "Data desconto inválida",
    "25": "Desconto maior que valor",
    "26": "Código juros inválido",
    "27": "Valor/data juros inválido",
    "28": "Código protesto inválido",
    "29": "Prazo protesto inválido",
    "30": "Pagador inválido",
    "40": "Título com pagamento vinculado",
    "45": "Nome beneficiário não informado",
    "46": "Tipo/nº inscrição beneficiário inválidos",
    "47": "Endereço beneficiário não informado",
    "48": "CEP inválido",
    "60": "Movimento não permitido para carteira",
    "63": "Entrada para título já cadastrado",
    "65": "Limite excedido",
    "77": "Alteração venc acima do permitido",
    "85": "Título com pagamento pendente",
    "86": "Seu número inválido",
    "88": "Cobrança sem código de barras",
    "97": "Erro qtd/valor total arquivo",
    "98": "Erro cadastro cedente",
    "99": "Outros motivos",
}


def _pint(s):
    s = s.strip()
    if not s or not s.lstrip("0"):
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _pdata(s):
    if not s or s == "00000000":
        return None
    try:
        return datetime.strptime(s, "%d%m%Y").date()
    except ValueError:
        return None


def _motivos(bloco10):
    out = []
    for i in range(5):
        c = bloco10[i * 2:i * 2 + 2]
        if c and c != "00":
            out.append({"codigo": c, "descricao": MOTIVOS.get(c, "Desconhecido")})
    return out


def _ha(l):
    return {
        "tipo": "header_arquivo",
        "banco": l[0:3],
        "cnpj": l[18:32],
        "agencia": l[52:57],
        "conta": l[58:70],
        "conta_dv": l[70],
        "razao_social": l[72:102].strip(),
        "data_geracao": _pdata(l[143:151]),
        "sequencial_arquivo": _pint(l[157:163]),
        "versao_layout": l[163:166],
    }


def _hl(l):
    return {
        "tipo": "header_lote",
        "lote": _pint(l[3:7]),
        "operacao": l[8],
        "servico": l[9:11],
        "data_gravacao": _pdata(l[191:199]),
        "data_credito": _pdata(l[199:207]),
    }


def _t(l):
    """Segmento T - offsets FEBRABAN 240"""
    return {
        "tipo": "segmento_t",
        "lote": _pint(l[3:7]),
        "sequencial": _pint(l[8:13]),
        "ocorrencia": l[15:17],
        "ocorrencia_desc": OCORRENCIAS.get(l[15:17], "Desconhecida"),
        "agencia": l[17:22],
        "conta": l[23:35],
        "nosso_numero": l[37:46].strip(),  # 9 chars uteis + 11 brancos
        "carteira": l[57],
        "seu_numero": l[58:73].strip(),
        "data_vencimento": _pdata(l[73:81]),
        "valor_titulo_centavos": _pint(l[81:96]),
        "banco_cobrador": l[96:99],
        "agencia_cobradora": l[99:104],
        "identificacao_titulo": l[105:130].strip(),
        "tipo_inscricao_pagador": l[130:131],
        "cpf_cnpj_pagador": l[131:146].lstrip("0"),
        "nome_pagador": l[146:186].strip(),
        "num_contrato": l[186:198].strip(),
        "valor_tarifa_centavos": _pint(l[198:213]),
        "motivos": _motivos(l[213:223]),
    }


def _u(l):
    """Segmento U - valores da liquidação"""
    return {
        "tipo": "segmento_u",
        "lote": _pint(l[3:7]),
        "sequencial": _pint(l[8:13]),
        "ocorrencia": l[15:17],
        "ocorrencia_desc": OCORRENCIAS.get(l[15:17], "Desconhecida"),
        "juros_multa_centavos": _pint(l[17:32]),
        "desconto_concedido_centavos": _pint(l[32:47]),
        "abatimento_concedido_centavos": _pint(l[47:62]),
        "iof_recolhido_centavos": _pint(l[62:77]),
        "valor_pago_centavos": _pint(l[77:92]),
        "valor_liquido_centavos": _pint(l[92:107]),
        "outras_despesas_centavos": _pint(l[107:122]),
        "outros_creditos_centavos": _pint(l[122:137]),
        "data_ocorrencia": _pdata(l[137:145]),
        "data_credito": _pdata(l[145:153]),
        "codigo_ocorrencia_pagador": l[153:157].strip(),
        "data_ocorrencia_pagador": _pdata(l[157:165]),
        "valor_ocorrencia_pagador_centavos": _pint(l[165:180]),
        "complemento": l[180:210].strip(),
    }


def _tl(l):
    return {
        "tipo": "trailer_lote",
        "lote": _pint(l[3:7]),
        "qtd_registros": _pint(l[17:23]),
        "qtd_titulos_cobranca_simples": _pint(l[23:29]),
        "valor_total_cobranca_simples_centavos": _pint(l[29:46]),
    }


def _ta(l):
    return {
        "tipo": "trailer_arquivo",
        "qtd_lotes": _pint(l[17:23]),
        "qtd_registros": _pint(l[23:29]),
    }


def parse_retorno(conteudo):
    linhas = [l for l in conteudo.replace("\r\n", "\n").split("\n") if l]
    if not linhas:
        raise ValueError("Arquivo retorno vazio")

    r = {
        "header_arquivo": None, "header_lote": None,
        "trailer_lote": None, "trailer_arquivo": None,
        "eventos": [], "erros_parse": [],
    }
    ev = None

    for i, l in enumerate(linhas, 1):
        if len(l) != 240:
            r["erros_parse"].append(f"Linha {i}: {len(l)} chars (esperado 240)")
            continue
        tr = l[7]
        if tr == "0":
            r["header_arquivo"] = _ha(l)
        elif tr == "1":
            r["header_lote"] = _hl(l)
        elif tr == "3":
            seg = l[13]
            if seg == "T":
                if ev is not None:
                    r["eventos"].append(ev)
                ev = _t(l)
            elif seg == "U":
                if ev is None:
                    r["erros_parse"].append(f"Linha {i}: U sem T anterior")
                    continue
                u = _u(l)
                ev["valores"] = {k: v for k, v in u.items()
                                 if k not in ("tipo", "lote", "sequencial")}
            elif seg == "W":
                pass  # PIX ignorado
            else:
                r["erros_parse"].append(f"Linha {i}: segmento inesperado '{seg}'")
        elif tr == "5":
            if ev is not None:
                r["eventos"].append(ev)
                ev = None
            r["trailer_lote"] = _tl(l)
        elif tr == "9":
            r["trailer_arquivo"] = _ta(l)
        else:
            r["erros_parse"].append(f"Linha {i}: tipo '{tr}' invalido")

    if ev is not None:
        r["eventos"].append(ev)
    return r


def classificar_evento(evento):
    """Simplifica um evento em status de negócio."""
    oc = evento.get("ocorrencia", "")
    if oc in ("02", "04"):
        status = "CONFIRMADO"
    elif oc in ("03", "26", "30"):
        status = "REJEITADO"
    elif oc in ("06", "08", "17", "46"):
        status = "LIQUIDADO"
    elif oc in ("05", "09", "10", "25", "40"):
        status = "BAIXADO"
    elif oc in ("07", "14", "27", "19", "20", "33", "34"):
        status = "ALTERADO"
    else:
        status = "OUTRO"

    v = evento.get("valores", {})
    return {
        "nosso_numero": evento.get("nosso_numero", "").lstrip("0") or "0",
        "seu_numero": evento.get("seu_numero", ""),
        "ocorrencia": oc,
        "ocorrencia_desc": evento.get("ocorrencia_desc", ""),
        "status": status,
        "valor_titulo_centavos": evento.get("valor_titulo_centavos", 0),
        "valor_pago_centavos": v.get("valor_pago_centavos", 0),
        "valor_liquido_centavos": v.get("valor_liquido_centavos", 0),
        "juros_multa_centavos": v.get("juros_multa_centavos", 0),
        "desconto_centavos": v.get("desconto_concedido_centavos", 0),
        "data_ocorrencia": v.get("data_ocorrencia"),
        "data_credito": v.get("data_credito"),
        "motivos_rejeicao": evento.get("motivos", []),
        "pagador_nome": evento.get("nome_pagador", ""),
        "pagador_doc": evento.get("cpf_cnpj_pagador", ""),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python3 retorno.py <arquivo.RET>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        r = parse_retorno(f.read())
    print(f"Header Arquivo: banco {r['header_arquivo']['banco']}"
          f" ag/conta {r['header_arquivo']['agencia']}/{r['header_arquivo']['conta']}"
          f" gerado {r['header_arquivo']['data_geracao']}")
    print(f"Eventos: {len(r['eventos'])}")
    for e in r["eventos"]:
        c = classificar_evento(e)
        motivos_str = ", ".join(f"{m['codigo']} {m['descricao']}" for m in c["motivos_rejeicao"]) or "-"
        print(f"  NN {c['nosso_numero']:>10}  {c['status']:>10}  oc {c['ocorrencia']} ({c['ocorrencia_desc']})"
              f"  pago R$ {c['valor_pago_centavos']/100:>10,.2f}"
              f"  liq R$ {c['valor_liquido_centavos']/100:>10,.2f}"
              f"  cred {c['data_credito']}  motivos: {motivos_str}")
    if r["erros_parse"]:
        print("\nERROS parse:")
        for e in r["erros_parse"]:
            print(f"  - {e}")
    print(f"\nTrailer Lote:    qtd_reg={r['trailer_lote']['qtd_registros']}"
          f" qtd_tit={r['trailer_lote']['qtd_titulos_cobranca_simples']}"
          f" valor_total=R$ {r['trailer_lote']['valor_total_cobranca_simples_centavos']/100:,.2f}")
    print(f"Trailer Arquivo: lotes={r['trailer_arquivo']['qtd_lotes']}"
          f" registros={r['trailer_arquivo']['qtd_registros']}")
