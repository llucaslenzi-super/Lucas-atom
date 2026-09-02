import { workflow, node, trigger, merge, expr } from '@n8n/workflow-sdk';

const CODE = "/**\n * Layout Safra CNAB 240 - agosto/2026 (portado de cnab240.py + boleto.py)\n *\n * Modulo puro (sem I/O). Chamado dentro de Code node do n8n.\n * Cada linha do arquivo REM tem exatamente 240 caracteres.\n */\n\n// ---------- Helpers ----------\n\nfunction alfa(v, tam) {\n  const s = (v == null ? '' : String(v)).toUpperCase();\n  return s.slice(0, tam).padEnd(tam, ' ');\n}\n\nfunction num(v, tam) {\n  const s = v == null ? '' : String(v);\n  return s.slice(-tam).padStart(tam, '0');\n}\n\nfunction fmtData(d) {\n  // d pode ser Date ou string YYYY-MM-DD\n  let date = d;\n  if (typeof d === 'string') date = new Date(d + 'T00:00:00Z');\n  if (!(date instanceof Date) || isNaN(date)) throw new Error('data invalida: ' + d);\n  const dd = String(date.getUTCDate()).padStart(2, '0');\n  const mm = String(date.getUTCMonth() + 1).padStart(2, '0');\n  const yy = String(date.getUTCFullYear());\n  return dd + mm + yy;\n}\n\nfunction assertLen(linha, tipo) {\n  if (linha.length !== 240) throw new Error(tipo + ': ' + linha.length + ' chars, esperado 240');\n  return linha;\n}\n\n// ---------- Registros ----------\n\nfunction headerArquivo(cfg, seqArquivo, dataGeracao) {\n  const parts = [\n    num(cfg.BANCO, 3),                          // 001-003\n    num('0', 4),                                // 004-007 Lote = 0000\n    num('0', 1),                                // 008     Tipo Registro\n    alfa('', 9),                                // 009-017 CNAB brancos\n    num('2', 1),                                // 018     Tipo Insc = 2 CNPJ\n    num(cfg.CNPJ, 14),                          // 019-032\n    alfa('', 20),                               // 033-052 Convenio\n    num(cfg.AGENCIA, 5),                        // 053-057\n    alfa('', 1),                                // 058     DV Ag\n    num(cfg.CONTA_NUMERO, 12),                  // 059-070\n    alfa(cfg.CONTA_DV, 1),                     // 071\n    alfa('', 1),                                // 072\n    alfa(cfg.RAZAO_SOCIAL, 30),                // 073-102\n    alfa('BANCO SAFRA S/A', 30),                // 103-132\n    alfa('', 10),                               // 133-142\n    num('1', 1),                                // 143 Remessa\n    num(fmtData(dataGeracao), 8),               // 144-151\n    num('0', 6),                                // 152-157 Hora\n    num(seqArquivo, 6),                         // 158-163\n    num(cfg.LAYOUT_VERSAO_ARQUIVO, 3),         // 164-166\n    alfa('', 5),                                // 167-171 Densidade\n    alfa('', 20),                               // 172-191\n    alfa('', 20),                               // 192-211\n    alfa('', 29),                               // 212-240\n  ];\n  return assertLen(parts.join(''), 'Header Arquivo');\n}\n\nfunction headerLote(cfg, numeroLote, dataGeracao) {\n  const parts = [\n    num(cfg.BANCO, 3),\n    num(numeroLote, 4),\n    num('1', 1),\n    alfa('R', 1),\n    num('01', 2),\n    alfa('', 2),\n    num(cfg.LAYOUT_VERSAO_LOTE, 3),\n    alfa('', 1),\n    num('2', 1),\n    num(cfg.CNPJ, 15),\n    alfa('', 20),\n    num(cfg.AGENCIA, 5),\n    alfa('', 1),\n    num(cfg.CONTA_NUMERO, 12),\n    alfa(cfg.CONTA_DV, 1),\n    alfa('', 1),\n    alfa(cfg.RAZAO_SOCIAL, 30),\n    alfa('', 40),\n    alfa('', 40),\n    num('1', 8),\n    num(fmtData(dataGeracao), 8),\n    num('0', 8),\n    alfa('', 33),\n  ];\n  return assertLen(parts.join(''), 'Header Lote');\n}\n\nfunction segmentoP(cfg, numeroLote, seqRegistro, titulo) {\n  // Nosso Numero 9 chars livres + 11 brancos (Safra ignora)\n  const nnField = num(titulo.nosso_numero, 9) + alfa('', 11);\n\n  // Regra Safra: cod juros=3 (isento) forca data=0 e valor=0\n  let jurosDataStr, jurosValor;\n  if (titulo.juros_codigo === '3') {\n    jurosDataStr = '00000000';\n    jurosValor = 0;\n  } else {\n    jurosDataStr = fmtData(titulo.juros_data);\n    jurosValor = titulo.juros_valor_centavos;\n  }\n  // Mesma regra pra desconto codigo 0\n  let descDataStr, descValor;\n  if (titulo.desconto_codigo === '0') {\n    descDataStr = '00000000';\n    descValor = 0;\n  } else {\n    descDataStr = fmtData(titulo.desconto_data);\n    descValor = titulo.desconto_valor_centavos;\n  }\n\n  const codMov = titulo.codigo_movimento || '01';\n\n  const parts = [\n    num(cfg.BANCO, 3),\n    num(numeroLote, 4),\n    num('3', 1),\n    num(seqRegistro, 5),\n    alfa('P', 1),\n    alfa('', 1),\n    num(codMov, 2),\n    num(cfg.AGENCIA, 5),\n    alfa('', 1),\n    num(cfg.CONTA_NUMERO, 12),\n    alfa(cfg.CONTA_DV, 1),\n    alfa('', 1),\n    nnField,\n    num(cfg.CARTEIRA, 1),\n    num(cfg.CADASTRO_TITULO, 1),\n    alfa(cfg.TIPO_DOCUMENTO, 1),\n    num(cfg.IDENTIFICACAO_BLOQUETO, 1),\n    alfa(cfg.DISTRIBUICAO_BLOQUETO, 1),\n    alfa(titulo.seu_numero, 15),\n    num(fmtData(titulo.data_vencimento), 8),\n    num(titulo.valor_centavos, 15),\n    num(cfg.AGENCIA, 5),\n    alfa('', 1),\n    num(titulo.especie, 2),\n    alfa('N', 1),\n    num(fmtData(titulo.data_emissao), 8),\n    num(titulo.juros_codigo, 1),\n    num(jurosDataStr, 8),\n    num(jurosValor, 15),\n    num(titulo.desconto_codigo, 1),\n    num(descDataStr, 8),\n    num(descValor, 15),\n    num('0', 15),\n    num('0', 15),\n    alfa(titulo.seu_numero, 25),\n    num(titulo.protesto_codigo, 1),\n    num(titulo.protesto_dias, 2),\n    num(titulo.baixa_codigo, 1),\n    alfa(num(titulo.baixa_dias, 3), 3),\n    num('09', 2),\n    num('0', 10),\n    alfa('1', 1),\n  ];\n  return assertLen(parts.join(''), 'Segmento P ' + titulo.nosso_numero);\n}\n\nfunction segmentoQ(cfg, numeroLote, seqRegistro, titulo) {\n  const p = titulo.pagador;\n  const codMov = titulo.codigo_movimento || '01';\n  const parts = [\n    num(cfg.BANCO, 3),\n    num(numeroLote, 4),\n    num('3', 1),\n    num(seqRegistro, 5),\n    alfa('Q', 1),\n    alfa('', 1),\n    num(codMov, 2),\n    num(p.tipo_inscricao, 1),\n    num(p.cpf_cnpj, 15),\n    alfa(p.nome, 40),\n    alfa(p.endereco, 40),\n    alfa(p.bairro, 15),\n    num(p.cep_prefixo, 5),\n    num(p.cep_sufixo, 3),\n    alfa(p.cidade, 15),\n    alfa(p.uf, 2),\n    num('0', 1),\n    num('0', 15),\n    alfa('', 40),\n    num('0', 3),\n    alfa('', 20),\n    alfa('', 8),\n  ];\n  return assertLen(parts.join(''), 'Segmento Q ' + titulo.nosso_numero);\n}\n\n// Segmento R - Multa. Emitido apenas se titulo tem multa (multa_codigo != '0').\nfunction segmentoR(cfg, numeroLote, seqRegistro, titulo) {\n  const codMov = titulo.codigo_movimento || '01';\n  const parts = [\n    num(cfg.BANCO, 3),                        // 001-003\n    num(numeroLote, 4),                       // 004-007\n    num('3', 1),                              // 008\n    num(seqRegistro, 5),                      // 009-013\n    alfa('R', 1),                             // 014\n    alfa('', 1),                              // 015\n    num(codMov, 2),                           // 016-017\n    num('0', 1),                              // 018 Cod Desc 2\n    num('0', 8),                              // 019-026 Data Desc 2\n    num('0', 15),                             // 027-041 Valor Desc 2\n    num('0', 1),                              // 042 Cod Desc 3\n    num('0', 8),                              // 043-050 Data Desc 3\n    num('0', 15),                             // 051-065 Valor Desc 3\n    num(titulo.multa_codigo, 1),              // 066 Cod Multa\n    num(fmtData(titulo.multa_data), 8),       // 067-074 Data Multa\n    num(Math.round(titulo.multa_percentual * 100), 15),  // 075-089 % Multa (2 dec impl)\n    alfa('', 10),                             // 090-099\n    alfa('', 40),                             // 100-139\n    alfa('', 40),                             // 140-179\n    alfa('', 20),                             // 180-199\n    alfa('', 8),                              // 200-207\n    alfa('', 3),                              // 208-210\n    alfa('', 5),                              // 211-215\n    alfa('', 1),                              // 216\n    alfa('', 12),                             // 217-228\n    alfa('', 1),                              // 229\n    alfa('', 1),                              // 230\n    alfa('', 1),                              // 231\n    alfa('', 9),                              // 232-240\n  ];\n  return assertLen(parts.join(''), 'Segmento R ' + titulo.nosso_numero);\n}\n\nfunction trailerLote(cfg, numeroLote, qtdRegistrosLote, qtdTitulos, valorTotalCentavos) {\n  const parts = [\n    num(cfg.BANCO, 3),\n    num(numeroLote, 4),\n    num('5', 1),\n    alfa('', 9),\n    num(qtdRegistrosLote, 6),\n    num(qtdTitulos, 6),\n    num(valorTotalCentavos, 17),\n    num('0', 6),\n    num('0', 17),\n    num('0', 6),\n    num('0', 17),\n    num('0', 6),\n    num('0', 17),\n    alfa('', 8),\n    alfa('', 117),\n  ];\n  return assertLen(parts.join(''), 'Trailer Lote');\n}\n\nfunction trailerArquivo(cfg, qtdLotes, qtdRegistrosArquivo) {\n  const parts = [\n    num(cfg.BANCO, 3),\n    num('9999', 4),\n    num('9', 1),\n    alfa('', 9),\n    num(qtdLotes, 6),\n    num(qtdRegistrosArquivo, 6),\n    num('0', 6),\n    alfa('', 205),\n  ];\n  return assertLen(parts.join(''), 'Trailer Arquivo');\n}\n\n/**\n * Monta o arquivo REM completo com N titulos.\n * Retorna string com linhas separadas por \\r\\n.\n */\nfunction gerarRemessa(cfg, titulos, seqArquivo, dataGeracao) {\n  const linhas = [];\n  const numeroLote = 1;\n  linhas.push(headerArquivo(cfg, seqArquivo, dataGeracao));\n  linhas.push(headerLote(cfg, numeroLote, dataGeracao));\n  let seq = 0;\n  let valorTotal = 0;\n  let qtdRegDetalhe = 0;\n  for (const t of titulos) {\n    seq++;\n    linhas.push(segmentoP(cfg, numeroLote, seq, t));\n    qtdRegDetalhe++;\n    seq++;\n    linhas.push(segmentoQ(cfg, numeroLote, seq, t));\n    qtdRegDetalhe++;\n    // Segmento R emitido apenas se titulo tem multa\n    if (t.multa_codigo && t.multa_codigo !== '0') {\n      seq++;\n      linhas.push(segmentoR(cfg, numeroLote, seq, t));\n      qtdRegDetalhe++;\n    }\n    valorTotal += t.valor_centavos;\n  }\n  const qtdRegLote = qtdRegDetalhe + 2; // + HL + TL\n  linhas.push(trailerLote(cfg, numeroLote, qtdRegLote, titulos.length, valorTotal));\n  const qtdRegArquivo = linhas.length + 1; // + Trailer Arquivo\n  linhas.push(trailerArquivo(cfg, 1, qtdRegArquivo));\n  return linhas.join('\\r\\n') + '\\r\\n';\n}\n\n// ---------- Comandos de movimento ----------\n// Wrappers que forcam o codigo_movimento e chamam gerarRemessa.\n// Cliente passa a mesma lista de titulos; cada titulo pode sobrescrever com titulo.codigo_movimento.\n\nfunction _clone(t, codMov) {\n  return Object.assign({}, t, { codigo_movimento: codMov });\n}\n\n// Entrada de titulos (default)\nfunction gerarRemessaEntrada(cfg, titulos, seqArquivo, dataGeracao) {\n  return gerarRemessa(cfg, titulos.map(t => _clone(t, '01')), seqArquivo, dataGeracao);\n}\n\n// Pedido de baixa (cod 02) - remessa so precisa de NN + valor do titulo original\nfunction gerarRemessaBaixa(cfg, titulos, seqArquivo, dataGeracao) {\n  return gerarRemessa(cfg, titulos.map(t => _clone(t, '02')), seqArquivo, dataGeracao);\n}\n\n// Alteracao vencimento (cod 06) - titulo precisa ter data_vencimento nova\nfunction gerarRemessaAlteracaoVenc(cfg, titulos, seqArquivo, dataGeracao) {\n  return gerarRemessa(cfg, titulos.map(t => _clone(t, '06')), seqArquivo, dataGeracao);\n}\n\n// Alteracao outros dados (cod 31) - juros/multa/desconto novos\nfunction gerarRemessaAlteracaoDados(cfg, titulos, seqArquivo, dataGeracao) {\n  return gerarRemessa(cfg, titulos.map(t => _clone(t, '31')), seqArquivo, dataGeracao);\n}\n\n// Pedido de protesto (cod 09)\nfunction gerarRemessaProtesto(cfg, titulos, seqArquivo, dataGeracao) {\n  return gerarRemessa(cfg, titulos.map(t => _clone(t, '09')), seqArquivo, dataGeracao);\n}\n\n// Sustar protesto (cod 10)\nfunction gerarRemessaSustarProtesto(cfg, titulos, seqArquivo, dataGeracao) {\n  return gerarRemessa(cfg, titulos.map(t => _clone(t, '10')), seqArquivo, dataGeracao);\n}\n\n// ---------- Parser RETORNO ----------\n\nconst RETORNO_OCORRENCIAS = {\n  '02': 'Entrada confirmada', '03': 'Entrada rejeitada',\n  '04': 'Transf carteira Entrada', '05': 'Transf carteira Baixa',\n  '06': 'Liquidacao normal', '07': 'Confirmacao alteracao',\n  '08': 'Liquidacao em cartorio', '09': 'Baixa', '10': 'Baixa por decurso prazo',\n  '11': 'Titulos em ser', '12': 'Confirmacao abatimento', '13': 'Cancelamento abatimento',\n  '14': 'Confirmacao alteracao vencimento', '17': 'Liquidacao apos baixa',\n  '19': 'Confirmacao pedido protesto', '20': 'Confirmacao sustacao protesto',\n  '23': 'Remessa a cartorio', '24': 'Retirada de cartorio', '25': 'Protestado e baixado',\n  '26': 'Instrucao rejeitada', '27': 'Confirmacao alt outros dados',\n  '28': 'Debito tarifas/custas', '29': 'Ocorrencias pagador',\n  '30': 'Alteracao dados rejeitada', '33': 'Confirmacao negativacao',\n  '34': 'Confirmacao exclusao negativacao', '40': 'Estorno pagamento',\n  '45': 'Titulo pago cheque devolvido', '46': 'Titulo pago cheque compensado',\n};\n\nconst RETORNO_MOTIVOS = {\n  '00': 'OK', '01': 'Cod banco invalido', '02': 'Cod registro invalido',\n  '03': 'Cod ocorrencia invalido', '04': 'Cod carteira invalido',\n  '05': 'Ag/conta invalido', '06': 'NN invalido', '07': 'NN duplicado',\n  '09': 'Ag/conta inexistente', '10': 'Titulo ja existe', '11': 'Titulo nao existe',\n  '15': 'Titulo ja baixado/liquidado', '17': 'Titulo ja em cartorio',\n  '18': 'Data venc invalida', '19': 'Venc anterior a emissao',\n  '21': 'Valor titulo invalido', '22': 'Especie invalida',\n  '26': 'Cod juros invalido', '28': 'Cod protesto invalido',\n  '30': 'Pagador invalido', '46': 'Tipo/nr insc beneficiario invalidos',\n  '48': 'CEP invalido', '60': 'Movimento nao permitido carteira',\n  '65': 'Limite excedido', '77': 'Alt venc acima permitido',\n  '85': 'Titulo com pagto pendente', '86': 'Seu numero invalido',\n  '97': 'Erro qtd/valor arquivo', '98': 'Erro cadastro cedente', '99': 'Outros',\n};\n\nfunction _pint(s) {\n  const t = String(s || '').trim();\n  if (!t || !t.replace(/^0+/, '')) return 0;\n  const n = parseInt(t, 10);\n  return isNaN(n) ? 0 : n;\n}\n\nfunction _pdata(s) {\n  if (!s || s === '00000000') return null;\n  const dd = s.slice(0, 2), mm = s.slice(2, 4), yy = s.slice(4, 8);\n  const d = new Date(Date.UTC(parseInt(yy, 10), parseInt(mm, 10) - 1, parseInt(dd, 10)));\n  return isNaN(d) ? null : d.toISOString().slice(0, 10);\n}\n\nfunction _motivos(bloco10) {\n  const out = [];\n  for (let i = 0; i < 5; i++) {\n    const c = bloco10.slice(i * 2, i * 2 + 2);\n    if (c && c !== '00') out.push({ codigo: c, descricao: RETORNO_MOTIVOS[c] || 'Desconhecido' });\n  }\n  return out;\n}\n\nfunction _parseSegT(l) {\n  return {\n    tipo: 'segmento_t',\n    lote: _pint(l.slice(3, 7)),\n    sequencial: _pint(l.slice(8, 13)),\n    ocorrencia: l.slice(15, 17),\n    ocorrencia_desc: RETORNO_OCORRENCIAS[l.slice(15, 17)] || 'Desconhecida',\n    agencia: l.slice(17, 22),\n    conta: l.slice(23, 35),\n    nosso_numero: l.slice(37, 46).trim(),\n    carteira: l.slice(57, 58),\n    seu_numero: l.slice(58, 73).trim(),\n    data_vencimento: _pdata(l.slice(73, 81)),\n    valor_titulo_centavos: _pint(l.slice(81, 96)),\n    banco_cobrador: l.slice(96, 99),\n    agencia_cobradora: l.slice(99, 104),\n    identificacao_titulo: l.slice(105, 130).trim(),\n    tipo_inscricao_pagador: l.slice(130, 131),\n    cpf_cnpj_pagador: l.slice(131, 146).replace(/^0+/, ''),\n    nome_pagador: l.slice(146, 186).trim(),\n    valor_tarifa_centavos: _pint(l.slice(198, 213)),\n    motivos: _motivos(l.slice(213, 223)),\n  };\n}\n\nfunction _parseSegU(l) {\n  return {\n    juros_multa_centavos: _pint(l.slice(17, 32)),\n    desconto_concedido_centavos: _pint(l.slice(32, 47)),\n    abatimento_concedido_centavos: _pint(l.slice(47, 62)),\n    iof_recolhido_centavos: _pint(l.slice(62, 77)),\n    valor_pago_centavos: _pint(l.slice(77, 92)),\n    valor_liquido_centavos: _pint(l.slice(92, 107)),\n    outras_despesas_centavos: _pint(l.slice(107, 122)),\n    outros_creditos_centavos: _pint(l.slice(122, 137)),\n    data_ocorrencia: _pdata(l.slice(137, 145)),\n    data_credito: _pdata(l.slice(145, 153)),\n  };\n}\n\nfunction parseRetorno(conteudo) {\n  const linhas = conteudo.replace(/\\r\\n/g, '\\n').split('\\n').filter(l => l.length > 0);\n  if (linhas.length === 0) throw new Error('Arquivo retorno vazio');\n  const r = { header_arquivo: null, header_lote: null, trailer_lote: null,\n              trailer_arquivo: null, eventos: [], erros_parse: [] };\n  let ev = null;\n  linhas.forEach((l, idx) => {\n    if (l.length !== 240) {\n      r.erros_parse.push('Linha ' + (idx + 1) + ': ' + l.length + ' chars');\n      return;\n    }\n    const tr = l[7];\n    if (tr === '0') {\n      r.header_arquivo = {\n        banco: l.slice(0, 3), cnpj: l.slice(18, 32),\n        agencia: l.slice(52, 57), conta: l.slice(58, 70),\n        razao_social: l.slice(72, 102).trim(),\n        data_geracao: _pdata(l.slice(143, 151)),\n      };\n    } else if (tr === '1') {\n      r.header_lote = { lote: _pint(l.slice(3, 7)), operacao: l[8] };\n    } else if (tr === '3') {\n      const seg = l[13];\n      if (seg === 'T') {\n        if (ev) r.eventos.push(ev);\n        ev = _parseSegT(l);\n      } else if (seg === 'U') {\n        if (!ev) { r.erros_parse.push('Linha ' + (idx + 1) + ': U sem T'); return; }\n        ev.valores = _parseSegU(l);\n      }\n    } else if (tr === '5') {\n      if (ev) { r.eventos.push(ev); ev = null; }\n      r.trailer_lote = {\n        qtd_registros: _pint(l.slice(17, 23)),\n        qtd_titulos: _pint(l.slice(23, 29)),\n        valor_total_centavos: _pint(l.slice(29, 46)),\n      };\n    } else if (tr === '9') {\n      r.trailer_arquivo = {\n        qtd_lotes: _pint(l.slice(17, 23)),\n        qtd_registros: _pint(l.slice(23, 29)),\n      };\n    }\n  });\n  if (ev) r.eventos.push(ev);\n  return r;\n}\n\nfunction classificarEvento(ev) {\n  const oc = ev.ocorrencia || '';\n  let status = 'OUTRO';\n  if (['02', '04'].includes(oc)) status = 'CONFIRMADO';\n  else if (['03', '26', '30'].includes(oc)) status = 'REJEITADO';\n  else if (['06', '08', '17', '46'].includes(oc)) status = 'LIQUIDADO';\n  else if (['05', '09', '10', '25', '40'].includes(oc)) status = 'BAIXADO';\n  else if (['07', '14', '27', '19', '20', '33', '34'].includes(oc)) status = 'ALTERADO';\n  const v = ev.valores || {};\n  return {\n    nosso_numero: (ev.nosso_numero || '').replace(/^0+/, '') || '0',\n    seu_numero: ev.seu_numero || '',\n    ocorrencia: oc,\n    ocorrencia_desc: ev.ocorrencia_desc || '',\n    status,\n    valor_titulo_centavos: ev.valor_titulo_centavos || 0,\n    valor_pago_centavos: v.valor_pago_centavos || 0,\n    valor_liquido_centavos: v.valor_liquido_centavos || 0,\n    juros_multa_centavos: v.juros_multa_centavos || 0,\n    desconto_centavos: v.desconto_concedido_centavos || 0,\n    data_ocorrencia: v.data_ocorrencia || null,\n    data_credito: v.data_credito || null,\n    motivos_rejeicao: ev.motivos || [],\n    pagador_nome: ev.nome_pagador || '',\n    pagador_doc: ev.cpf_cnpj_pagador || '',\n  };\n}\n\n// ---------- BOLETO: fator, DAC, DV, CB, LD ----------\n\nconst DATA_BASE_FATOR = new Date(Date.UTC(2022, 4, 29));  // 29/05/2022\n\nfunction fatorVencimento(dataVenc) {\n  let d = dataVenc;\n  if (typeof d === 'string') d = new Date(d + 'T00:00:00Z');\n  const delta = Math.floor((d - DATA_BASE_FATOR) / (1000 * 60 * 60 * 24));\n  if (delta < 1000) throw new Error('vencimento anterior a 22/02/2025 - fator invalido no layout novo');\n  if (delta > 9999) return ((delta - 1000) % 9000) + 1000;\n  return delta;\n}\n\nfunction dacCodigoBarras(barras43) {\n  if (barras43.length !== 43) throw new Error('barras43 tem ' + barras43.length + ' chars');\n  const pesos = [2, 3, 4, 5, 6, 7, 8, 9];\n  let soma = 0;\n  const rev = barras43.split('').reverse();\n  for (let i = 0; i < rev.length; i++) {\n    soma += parseInt(rev[i], 10) * pesos[i % 8];\n  }\n  const resto = soma % 11;\n  if (resto === 0 || resto === 1 || resto === 10) return '1';\n  return String(11 - resto);\n}\n\nfunction dvModulo10(campo) {\n  let soma = 0;\n  let peso = 2;\n  const rev = campo.split('').reverse();\n  for (const ch of rev) {\n    const produto = parseInt(ch, 10) * peso;\n    soma += Math.floor(produto / 10) + (produto % 10);\n    peso = peso === 2 ? 1 : 2;\n  }\n  const resto = soma % 10;\n  return resto === 0 ? '0' : String(10 - resto);\n}\n\nfunction codigoBarras44(cfg, nossoNumero, dataVenc, valorCentavos) {\n  const fator = fatorVencimento(dataVenc);\n  const campoLivre = (\n    cfg.SISTEMA_SAFRA +\n    cfg.AGENCIA +\n    cfg.CONTA_COMPLETA +\n    String(nossoNumero).padStart(9, '0') +\n    '2'  // Tipo Cobranca Registrada\n  );\n  if (campoLivre.length !== 25) throw new Error('campo_livre len=' + campoLivre.length);\n  const valorStr = String(valorCentavos).padStart(10, '0');\n  const barrasSemDac = (\n    cfg.BANCO +\n    '9' +\n    String(fator).padStart(4, '0') +\n    valorStr +\n    campoLivre\n  );\n  if (barrasSemDac.length !== 43) throw new Error('barras sem dac len=' + barrasSemDac.length);\n  const dac = dacCodigoBarras(barrasSemDac);\n  return barrasSemDac.slice(0, 4) + dac + barrasSemDac.slice(4);\n}\n\nfunction linhaDigitavel(codBarras) {\n  if (codBarras.length !== 44) throw new Error('cb len=' + codBarras.length);\n  const banco = codBarras.slice(0, 3);\n  const moeda = codBarras.slice(3, 4);\n  const dac = codBarras.slice(4, 5);\n  const fator = codBarras.slice(5, 9);\n  const valor = codBarras.slice(9, 19);\n  const cl = codBarras.slice(19, 44);\n  const sistema = cl.slice(0, 1);\n  const agencia = cl.slice(1, 6);\n  const conta = cl.slice(6, 15);\n  const nn = cl.slice(15, 24);\n  const tipoCob = cl.slice(24, 25);\n  const c1 = banco + moeda + sistema + agencia.slice(0, 4);\n  const c1dv = dvModulo10(c1);\n  const c2 = agencia.slice(4) + conta;\n  const c2dv = dvModulo10(c2);\n  const c3 = nn + tipoCob;\n  const c3dv = dvModulo10(c3);\n  const c5 = fator + valor;\n  return (\n    c1.slice(0, 5) + '.' + c1.slice(5) + c1dv + ' ' +\n    c2.slice(0, 5) + '.' + c2.slice(5) + c2dv + ' ' +\n    c3.slice(0, 5) + '.' + c3.slice(5) + c3dv + ' ' +\n    dac + ' ' +\n    c5\n  );\n}\n\n// Exporta se rodar em Node standalone (pra teste), senao ignora\nif (typeof module !== 'undefined' && module.exports) {\n  module.exports = {\n    alfa, num, fmtData,\n    headerArquivo, headerLote, segmentoP, segmentoQ, segmentoR,\n    trailerLote, trailerArquivo, gerarRemessa,\n    gerarRemessaEntrada, gerarRemessaBaixa, gerarRemessaAlteracaoVenc,\n    gerarRemessaAlteracaoDados, gerarRemessaProtesto, gerarRemessaSustarProtesto,\n    parseRetorno, classificarEvento,\n    RETORNO_OCORRENCIAS, RETORNO_MOTIVOS,\n    fatorVencimento, dacCodigoBarras, dvModulo10, codigoBarras44, linhaDigitavel,\n  };\n}\n\n\n\n// ====== ROUTER SAFRA ======\n// Recebe items com { action, env, payload } vindos do Normalize.\n// Devolve items com { ok, action, env, resultado } pro Respond.\n\nconst CFG = {\n  BANCO: '422',\n  AGENCIA: '02900',\n  CONTA_NUMERO: '00587521',\n  CONTA_DV: '6',\n  CONTA_COMPLETA: '005875216',\n  CNPJ: '35588873000141',\n  RAZAO_SOCIAL: 'SOUL INDUSTRIA DE TECIDOS LTDA',\n  CARTEIRA: '1',\n  LAYOUT_VERSAO_ARQUIVO: '103',\n  LAYOUT_VERSAO_LOTE: '060',\n  CADASTRO_TITULO: '1',\n  TIPO_DOCUMENTO: '2',\n  IDENTIFICACAO_BLOQUETO: '2',\n  DISTRIBUICAO_BLOQUETO: '2',\n  SISTEMA_SAFRA: '7',\n};\n\nconst results = [];\nfor (const item of $input.all()) {\n  const body = item.json;\n  const action = String(body.action || '').toLowerCase();\n  const env = String(body.env || 'sandbox').toLowerCase();\n\n  // PROD bloqueado por default. Retorna erro claro se tentar.\n  if (env === 'prod' || env === 'production') {\n    results.push({\n      json: {\n        ok: false,\n        action,\n        env,\n        erro: 'PROD_BLOQUEADO',\n        mensagem: 'Emissao em producao esta bloqueada. Use env=sandbox pra homologacao.',\n      },\n    });\n    continue;\n  }\n\n  let resultado;\n  try {\n    if (action === 'emitir') {\n      // Simula emissao: gera REM de entrada, devolve conteudo + CB + LD\n      const titulos = body.titulos || [];\n      if (!titulos.length) throw new Error('titulos vazio');\n      const rem = gerarRemessaEntrada(CFG, titulos, body.seq_arquivo || 1, new Date());\n      const boletos = [];\n      for (const t of titulos) {\n        const cb = codigoBarras44(CFG, t.nosso_numero, t.data_vencimento, t.valor_centavos);\n        const ld = linhaDigitavel(cb);\n        boletos.push({ nosso_numero: t.nosso_numero, cb, ld });\n      }\n      resultado = {\n        rem_bytes: rem.length,\n        rem_linhas: rem.split('\\r\\n').filter(l => l).length,\n        boletos,\n        // conteudo_rem: rem,   // omitido no default - pode ser gigante\n      };\n      if (body.include_rem_content) resultado.conteudo_rem = rem;\n\n    } else if (action === 'consultar') {\n      // Simula consulta - devolve status \"SIMULADO\" (real leria Data Table)\n      const nn = String(body.nosso_numero || '').padStart(9, '0');\n      resultado = {\n        nosso_numero: nn,\n        status: 'SIMULADO',\n        mensagem: 'Consulta real leria Data Table safra_titulos_gerados',\n      };\n\n    } else if (action === 'alterar' || action === 'alterar_venc' || action === 'alterar_dados') {\n      // Simula alteracao - devolve REM que seria enfileirado\n      const titulos = body.titulos || [];\n      if (!titulos.length) throw new Error('titulos vazio');\n      const fn = action === 'alterar_venc' ? gerarRemessaAlteracaoVenc : gerarRemessaAlteracaoDados;\n      const rem = fn(CFG, titulos, body.seq_arquivo || 1, new Date());\n      resultado = {\n        codigo_movimento: action === 'alterar_venc' ? '06' : '31',\n        rem_bytes: rem.length,\n        rem_linhas: rem.split('\\r\\n').filter(l => l).length,\n      };\n      if (body.include_rem_content) resultado.conteudo_rem = rem;\n\n    } else if (action === 'baixar') {\n      const titulos = body.titulos || [];\n      if (!titulos.length) throw new Error('titulos vazio');\n      const rem = gerarRemessaBaixa(CFG, titulos, body.seq_arquivo || 1, new Date());\n      resultado = {\n        codigo_movimento: '02',\n        rem_bytes: rem.length,\n        rem_linhas: rem.split('\\r\\n').filter(l => l).length,\n      };\n      if (body.include_rem_content) resultado.conteudo_rem = rem;\n\n    } else if (action === 'processar_retorno' || action === 'retorno') {\n      // Parse do .RET vindo em body.conteudo_ret (string) ou body.conteudo_base64\n      let conteudo = body.conteudo_ret;\n      if (!conteudo && body.conteudo_base64) {\n        conteudo = Buffer.from(body.conteudo_base64, 'base64').toString('latin1');\n      }\n      if (!conteudo) throw new Error('falta conteudo_ret ou conteudo_base64');\n      const parsed = parseRetorno(conteudo);\n      resultado = {\n        header_arquivo: parsed.header_arquivo,\n        qtd_eventos: parsed.eventos.length,\n        eventos: parsed.eventos.map(e => classificarEvento(e)),\n        trailer_lote: parsed.trailer_lote,\n        trailer_arquivo: parsed.trailer_arquivo,\n        erros_parse: parsed.erros_parse,\n      };\n\n    } else {\n      throw new Error('action desconhecida: ' + action);\n    }\n\n    results.push({ json: { ok: true, action, env, resultado } });\n  } catch (e) {\n    results.push({ json: { ok: false, action, env, erro: String(e.message || e) } });\n  }\n}\nreturn results;\n";

const webhookEmitir = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Emitir',
    parameters: {
      path: 'safra-emitir',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'emitir' } }],
});

const webhookConsultar = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Consultar',
    parameters: {
      path: 'safra-consultar',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'consultar' } }],
});

const webhookAlterar = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Alterar',
    parameters: {
      path: 'safra-alterar',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'alterar_venc' } }],
});

const webhookBaixar = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Baixar',
    parameters: {
      path: 'safra-baixar',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'baixar' } }],
});

const webhookRetorno = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Processar Retorno',
    parameters: {
      path: 'safra-processar-retorno',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'processar_retorno' } }],
});

const normalizeEmitir = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Emitir',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'emitir', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'titulos', name: 'titulos', value: expr("{{ $json.body?.titulos ?? [] }}"), type: 'array' },
          { id: 'seq_arquivo', name: 'seq_arquivo', value: expr("{{ $json.body?.seq_arquivo ?? 1 }}"), type: 'number' },
          { id: 'include_rem_content', name: 'include_rem_content', value: expr("{{ $json.body?.include_rem_content ?? false }}"), type: 'boolean' },
        ],
      },
    },
  },
  output: [{ action: 'emitir', env: 'sandbox', titulos: [], seq_arquivo: 1, include_rem_content: false }],
});

const normalizeConsultar = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Consultar',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'consultar', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'nosso_numero', name: 'nosso_numero', value: expr("{{ $json.body?.nosso_numero ?? '' }}"), type: 'string' },
        ],
      },
    },
  },
  output: [{ action: 'consultar', env: 'sandbox', nosso_numero: '' }],
});

const normalizeAlterar = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Alterar',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: expr("{{ $json.body?.action ?? 'alterar_venc' }}"), type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'titulos', name: 'titulos', value: expr("{{ $json.body?.titulos ?? [] }}"), type: 'array' },
          { id: 'seq_arquivo', name: 'seq_arquivo', value: expr("{{ $json.body?.seq_arquivo ?? 1 }}"), type: 'number' },
          { id: 'include_rem_content', name: 'include_rem_content', value: expr("{{ $json.body?.include_rem_content ?? false }}"), type: 'boolean' },
        ],
      },
    },
  },
  output: [{ action: 'alterar_venc', env: 'sandbox', titulos: [], seq_arquivo: 1, include_rem_content: false }],
});

const normalizeBaixar = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Baixar',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'baixar', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'titulos', name: 'titulos', value: expr("{{ $json.body?.titulos ?? [] }}"), type: 'array' },
          { id: 'seq_arquivo', name: 'seq_arquivo', value: expr("{{ $json.body?.seq_arquivo ?? 1 }}"), type: 'number' },
          { id: 'include_rem_content', name: 'include_rem_content', value: expr("{{ $json.body?.include_rem_content ?? false }}"), type: 'boolean' },
        ],
      },
    },
  },
  output: [{ action: 'baixar', env: 'sandbox', titulos: [], seq_arquivo: 1, include_rem_content: false }],
});

const normalizeRetorno = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Retorno',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'processar_retorno', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'conteudo_ret', name: 'conteudo_ret', value: expr("{{ $json.body?.conteudo_ret ?? '' }}"), type: 'string' },
          { id: 'conteudo_base64', name: 'conteudo_base64', value: expr("{{ $json.body?.conteudo_base64 ?? '' }}"), type: 'string' },
        ],
      },
    },
  },
  output: [{ action: 'processar_retorno', env: 'sandbox', conteudo_ret: '', conteudo_base64: '' }],
});

const codeRouter = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Safra Router',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: CODE,
    },
  },
  output: [{ ok: true, action: 'emitir', env: 'sandbox', resultado: {} }],
});

const respond = node({
  type: 'n8n-nodes-base.respondToWebhook',
  version: 1.5,
  config: {
    name: 'Respond',
    parameters: {
      respondWith: 'json',
      responseBody: expr("{{ JSON.stringify($json) }}"),
      options: { responseCode: 200 },
    },
  },
});

export default workflow('agente-boletos-safra', 'Agente Boletos Safra')
  .add(webhookEmitir).to(normalizeEmitir).to(codeRouter).to(respond)
  .add(webhookConsultar).to(normalizeConsultar).to(codeRouter)
  .add(webhookAlterar).to(normalizeAlterar).to(codeRouter)
  .add(webhookBaixar).to(normalizeBaixar).to(codeRouter)
  .add(webhookRetorno).to(normalizeRetorno).to(codeRouter);
