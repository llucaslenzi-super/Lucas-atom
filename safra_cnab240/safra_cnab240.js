/**
 * Layout Safra CNAB 240 - agosto/2026 (portado de cnab240.py + boleto.py)
 *
 * Modulo puro (sem I/O). Chamado dentro de Code node do n8n.
 * Cada linha do arquivo REM tem exatamente 240 caracteres.
 */

// ---------- Helpers ----------

function alfa(v, tam) {
  const s = (v == null ? '' : String(v)).toUpperCase();
  return s.slice(0, tam).padEnd(tam, ' ');
}

function num(v, tam) {
  const s = v == null ? '' : String(v);
  return s.slice(-tam).padStart(tam, '0');
}

function fmtData(d) {
  // d pode ser Date ou string YYYY-MM-DD
  let date = d;
  if (typeof d === 'string') date = new Date(d + 'T00:00:00Z');
  if (!(date instanceof Date) || isNaN(date)) throw new Error('data invalida: ' + d);
  const dd = String(date.getUTCDate()).padStart(2, '0');
  const mm = String(date.getUTCMonth() + 1).padStart(2, '0');
  const yy = String(date.getUTCFullYear());
  return dd + mm + yy;
}

function assertLen(linha, tipo) {
  if (linha.length !== 240) throw new Error(tipo + ': ' + linha.length + ' chars, esperado 240');
  return linha;
}

// ---------- Registros ----------

function headerArquivo(cfg, seqArquivo, dataGeracao) {
  const parts = [
    num(cfg.BANCO, 3),                          // 001-003
    num('0', 4),                                // 004-007 Lote = 0000
    num('0', 1),                                // 008     Tipo Registro
    alfa('', 9),                                // 009-017 CNAB brancos
    num('2', 1),                                // 018     Tipo Insc = 2 CNPJ
    num(cfg.CNPJ, 14),                          // 019-032
    alfa('', 20),                               // 033-052 Convenio
    num(cfg.AGENCIA, 5),                        // 053-057
    alfa('', 1),                                // 058     DV Ag
    num(cfg.CONTA_NUMERO, 12),                  // 059-070
    alfa(cfg.CONTA_DV, 1),                     // 071
    alfa('', 1),                                // 072
    alfa(cfg.RAZAO_SOCIAL, 30),                // 073-102
    alfa('BANCO SAFRA S/A', 30),                // 103-132
    alfa('', 10),                               // 133-142
    num('1', 1),                                // 143 Remessa
    num(fmtData(dataGeracao), 8),               // 144-151
    num('0', 6),                                // 152-157 Hora
    num(seqArquivo, 6),                         // 158-163
    num(cfg.LAYOUT_VERSAO_ARQUIVO, 3),         // 164-166
    alfa('', 5),                                // 167-171 Densidade
    alfa('', 20),                               // 172-191
    alfa('', 20),                               // 192-211
    alfa('', 29),                               // 212-240
  ];
  return assertLen(parts.join(''), 'Header Arquivo');
}

function headerLote(cfg, numeroLote, dataGeracao) {
  const parts = [
    num(cfg.BANCO, 3),
    num(numeroLote, 4),
    num('1', 1),
    alfa('R', 1),
    num('01', 2),
    alfa('', 2),
    num(cfg.LAYOUT_VERSAO_LOTE, 3),
    alfa('', 1),
    num('2', 1),
    num(cfg.CNPJ, 15),
    alfa('', 20),
    num(cfg.AGENCIA, 5),
    alfa('', 1),
    num(cfg.CONTA_NUMERO, 12),
    alfa(cfg.CONTA_DV, 1),
    alfa('', 1),
    alfa(cfg.RAZAO_SOCIAL, 30),
    alfa('', 40),
    alfa('', 40),
    num('1', 8),
    num(fmtData(dataGeracao), 8),
    num('0', 8),
    alfa('', 33),
  ];
  return assertLen(parts.join(''), 'Header Lote');
}

function segmentoP(cfg, numeroLote, seqRegistro, titulo) {
  // Nosso Numero 9 chars livres + 11 brancos (Safra ignora)
  const nnField = num(titulo.nosso_numero, 9) + alfa('', 11);

  // Regra Safra: cod juros=3 (isento) forca data=0 e valor=0
  let jurosDataStr, jurosValor;
  if (titulo.juros_codigo === '3') {
    jurosDataStr = '00000000';
    jurosValor = 0;
  } else {
    jurosDataStr = fmtData(titulo.juros_data);
    jurosValor = titulo.juros_valor_centavos;
  }
  // Mesma regra pra desconto codigo 0
  let descDataStr, descValor;
  if (titulo.desconto_codigo === '0') {
    descDataStr = '00000000';
    descValor = 0;
  } else {
    descDataStr = fmtData(titulo.desconto_data);
    descValor = titulo.desconto_valor_centavos;
  }

  const codMov = titulo.codigo_movimento || '01';

  const parts = [
    num(cfg.BANCO, 3),
    num(numeroLote, 4),
    num('3', 1),
    num(seqRegistro, 5),
    alfa('P', 1),
    alfa('', 1),
    num(codMov, 2),
    num(cfg.AGENCIA, 5),
    alfa('', 1),
    num(cfg.CONTA_NUMERO, 12),
    alfa(cfg.CONTA_DV, 1),
    alfa('', 1),
    nnField,
    num(cfg.CARTEIRA, 1),
    num(cfg.CADASTRO_TITULO, 1),
    alfa(cfg.TIPO_DOCUMENTO, 1),
    num(cfg.IDENTIFICACAO_BLOQUETO, 1),
    alfa(cfg.DISTRIBUICAO_BLOQUETO, 1),
    alfa(titulo.seu_numero, 15),
    num(fmtData(titulo.data_vencimento), 8),
    num(titulo.valor_centavos, 15),
    num(cfg.AGENCIA, 5),
    alfa('', 1),
    num(titulo.especie, 2),
    alfa('N', 1),
    num(fmtData(titulo.data_emissao), 8),
    num(titulo.juros_codigo, 1),
    num(jurosDataStr, 8),
    num(jurosValor, 15),
    num(titulo.desconto_codigo, 1),
    num(descDataStr, 8),
    num(descValor, 15),
    num('0', 15),
    num('0', 15),
    alfa(titulo.seu_numero, 25),
    num(titulo.protesto_codigo, 1),
    num(titulo.protesto_dias, 2),
    num(titulo.baixa_codigo, 1),
    alfa(num(titulo.baixa_dias, 3), 3),
    num('09', 2),
    num('0', 10),
    alfa('1', 1),
  ];
  return assertLen(parts.join(''), 'Segmento P ' + titulo.nosso_numero);
}

function segmentoQ(cfg, numeroLote, seqRegistro, titulo) {
  const p = titulo.pagador;
  const codMov = titulo.codigo_movimento || '01';
  const parts = [
    num(cfg.BANCO, 3),
    num(numeroLote, 4),
    num('3', 1),
    num(seqRegistro, 5),
    alfa('Q', 1),
    alfa('', 1),
    num(codMov, 2),
    num(p.tipo_inscricao, 1),
    num(p.cpf_cnpj, 15),
    alfa(p.nome, 40),
    alfa(p.endereco, 40),
    alfa(p.bairro, 15),
    num(p.cep_prefixo, 5),
    num(p.cep_sufixo, 3),
    alfa(p.cidade, 15),
    alfa(p.uf, 2),
    num('0', 1),
    num('0', 15),
    alfa('', 40),
    num('0', 3),
    alfa('', 20),
    alfa('', 8),
  ];
  return assertLen(parts.join(''), 'Segmento Q ' + titulo.nosso_numero);
}

// Segmento R - Multa. Emitido apenas se titulo tem multa (multa_codigo != '0').
function segmentoR(cfg, numeroLote, seqRegistro, titulo) {
  const codMov = titulo.codigo_movimento || '01';
  const parts = [
    num(cfg.BANCO, 3),                        // 001-003
    num(numeroLote, 4),                       // 004-007
    num('3', 1),                              // 008
    num(seqRegistro, 5),                      // 009-013
    alfa('R', 1),                             // 014
    alfa('', 1),                              // 015
    num(codMov, 2),                           // 016-017
    num('0', 1),                              // 018 Cod Desc 2
    num('0', 8),                              // 019-026 Data Desc 2
    num('0', 15),                             // 027-041 Valor Desc 2
    num('0', 1),                              // 042 Cod Desc 3
    num('0', 8),                              // 043-050 Data Desc 3
    num('0', 15),                             // 051-065 Valor Desc 3
    num(titulo.multa_codigo, 1),              // 066 Cod Multa
    num(fmtData(titulo.multa_data), 8),       // 067-074 Data Multa
    num(Math.round(titulo.multa_percentual * 100), 15),  // 075-089 % Multa (2 dec impl)
    alfa('', 10),                             // 090-099
    alfa('', 40),                             // 100-139
    alfa('', 40),                             // 140-179
    alfa('', 20),                             // 180-199
    alfa('', 8),                              // 200-207
    alfa('', 3),                              // 208-210
    alfa('', 5),                              // 211-215
    alfa('', 1),                              // 216
    alfa('', 12),                             // 217-228
    alfa('', 1),                              // 229
    alfa('', 1),                              // 230
    alfa('', 1),                              // 231
    alfa('', 9),                              // 232-240
  ];
  return assertLen(parts.join(''), 'Segmento R ' + titulo.nosso_numero);
}

function trailerLote(cfg, numeroLote, qtdRegistrosLote, qtdTitulos, valorTotalCentavos) {
  const parts = [
    num(cfg.BANCO, 3),
    num(numeroLote, 4),
    num('5', 1),
    alfa('', 9),
    num(qtdRegistrosLote, 6),
    num(qtdTitulos, 6),
    num(valorTotalCentavos, 17),
    num('0', 6),
    num('0', 17),
    num('0', 6),
    num('0', 17),
    num('0', 6),
    num('0', 17),
    alfa('', 8),
    alfa('', 117),
  ];
  return assertLen(parts.join(''), 'Trailer Lote');
}

function trailerArquivo(cfg, qtdLotes, qtdRegistrosArquivo) {
  const parts = [
    num(cfg.BANCO, 3),
    num('9999', 4),
    num('9', 1),
    alfa('', 9),
    num(qtdLotes, 6),
    num(qtdRegistrosArquivo, 6),
    num('0', 6),
    alfa('', 205),
  ];
  return assertLen(parts.join(''), 'Trailer Arquivo');
}

/**
 * Monta o arquivo REM completo com N titulos.
 * Retorna string com linhas separadas por \r\n.
 */
function gerarRemessa(cfg, titulos, seqArquivo, dataGeracao) {
  const linhas = [];
  const numeroLote = 1;
  linhas.push(headerArquivo(cfg, seqArquivo, dataGeracao));
  linhas.push(headerLote(cfg, numeroLote, dataGeracao));
  let seq = 0;
  let valorTotal = 0;
  let qtdRegDetalhe = 0;
  for (const t of titulos) {
    seq++;
    linhas.push(segmentoP(cfg, numeroLote, seq, t));
    qtdRegDetalhe++;
    seq++;
    linhas.push(segmentoQ(cfg, numeroLote, seq, t));
    qtdRegDetalhe++;
    // Segmento R emitido apenas se titulo tem multa
    if (t.multa_codigo && t.multa_codigo !== '0') {
      seq++;
      linhas.push(segmentoR(cfg, numeroLote, seq, t));
      qtdRegDetalhe++;
    }
    valorTotal += t.valor_centavos;
  }
  const qtdRegLote = qtdRegDetalhe + 2; // + HL + TL
  linhas.push(trailerLote(cfg, numeroLote, qtdRegLote, titulos.length, valorTotal));
  const qtdRegArquivo = linhas.length + 1; // + Trailer Arquivo
  linhas.push(trailerArquivo(cfg, 1, qtdRegArquivo));
  return linhas.join('\r\n') + '\r\n';
}

// ---------- Comandos de movimento ----------
// Wrappers que forcam o codigo_movimento e chamam gerarRemessa.
// Cliente passa a mesma lista de titulos; cada titulo pode sobrescrever com titulo.codigo_movimento.

function _clone(t, codMov) {
  return Object.assign({}, t, { codigo_movimento: codMov });
}

// Entrada de titulos (default)
function gerarRemessaEntrada(cfg, titulos, seqArquivo, dataGeracao) {
  return gerarRemessa(cfg, titulos.map(t => _clone(t, '01')), seqArquivo, dataGeracao);
}

// Pedido de baixa (cod 02) - remessa so precisa de NN + valor do titulo original
function gerarRemessaBaixa(cfg, titulos, seqArquivo, dataGeracao) {
  return gerarRemessa(cfg, titulos.map(t => _clone(t, '02')), seqArquivo, dataGeracao);
}

// Alteracao vencimento (cod 06) - titulo precisa ter data_vencimento nova
function gerarRemessaAlteracaoVenc(cfg, titulos, seqArquivo, dataGeracao) {
  return gerarRemessa(cfg, titulos.map(t => _clone(t, '06')), seqArquivo, dataGeracao);
}

// Alteracao outros dados (cod 31) - juros/multa/desconto novos
function gerarRemessaAlteracaoDados(cfg, titulos, seqArquivo, dataGeracao) {
  return gerarRemessa(cfg, titulos.map(t => _clone(t, '31')), seqArquivo, dataGeracao);
}

// Pedido de protesto (cod 09)
function gerarRemessaProtesto(cfg, titulos, seqArquivo, dataGeracao) {
  return gerarRemessa(cfg, titulos.map(t => _clone(t, '09')), seqArquivo, dataGeracao);
}

// Sustar protesto (cod 10)
function gerarRemessaSustarProtesto(cfg, titulos, seqArquivo, dataGeracao) {
  return gerarRemessa(cfg, titulos.map(t => _clone(t, '10')), seqArquivo, dataGeracao);
}

// ---------- Parser RETORNO ----------

const RETORNO_OCORRENCIAS = {
  '02': 'Entrada confirmada', '03': 'Entrada rejeitada',
  '04': 'Transf carteira Entrada', '05': 'Transf carteira Baixa',
  '06': 'Liquidacao normal', '07': 'Confirmacao alteracao',
  '08': 'Liquidacao em cartorio', '09': 'Baixa', '10': 'Baixa por decurso prazo',
  '11': 'Titulos em ser', '12': 'Confirmacao abatimento', '13': 'Cancelamento abatimento',
  '14': 'Confirmacao alteracao vencimento', '17': 'Liquidacao apos baixa',
  '19': 'Confirmacao pedido protesto', '20': 'Confirmacao sustacao protesto',
  '23': 'Remessa a cartorio', '24': 'Retirada de cartorio', '25': 'Protestado e baixado',
  '26': 'Instrucao rejeitada', '27': 'Confirmacao alt outros dados',
  '28': 'Debito tarifas/custas', '29': 'Ocorrencias pagador',
  '30': 'Alteracao dados rejeitada', '33': 'Confirmacao negativacao',
  '34': 'Confirmacao exclusao negativacao', '40': 'Estorno pagamento',
  '45': 'Titulo pago cheque devolvido', '46': 'Titulo pago cheque compensado',
};

const RETORNO_MOTIVOS = {
  '00': 'OK', '01': 'Cod banco invalido', '02': 'Cod registro invalido',
  '03': 'Cod ocorrencia invalido', '04': 'Cod carteira invalido',
  '05': 'Ag/conta invalido', '06': 'NN invalido', '07': 'NN duplicado',
  '09': 'Ag/conta inexistente', '10': 'Titulo ja existe', '11': 'Titulo nao existe',
  '15': 'Titulo ja baixado/liquidado', '17': 'Titulo ja em cartorio',
  '18': 'Data venc invalida', '19': 'Venc anterior a emissao',
  '21': 'Valor titulo invalido', '22': 'Especie invalida',
  '26': 'Cod juros invalido', '28': 'Cod protesto invalido',
  '30': 'Pagador invalido', '46': 'Tipo/nr insc beneficiario invalidos',
  '48': 'CEP invalido', '60': 'Movimento nao permitido carteira',
  '65': 'Limite excedido', '77': 'Alt venc acima permitido',
  '85': 'Titulo com pagto pendente', '86': 'Seu numero invalido',
  '97': 'Erro qtd/valor arquivo', '98': 'Erro cadastro cedente', '99': 'Outros',
};

function _pint(s) {
  const t = String(s || '').trim();
  if (!t || !t.replace(/^0+/, '')) return 0;
  const n = parseInt(t, 10);
  return isNaN(n) ? 0 : n;
}

function _pdata(s) {
  if (!s || s === '00000000') return null;
  const dd = s.slice(0, 2), mm = s.slice(2, 4), yy = s.slice(4, 8);
  const d = new Date(Date.UTC(parseInt(yy, 10), parseInt(mm, 10) - 1, parseInt(dd, 10)));
  return isNaN(d) ? null : d.toISOString().slice(0, 10);
}

function _motivos(bloco10) {
  const out = [];
  for (let i = 0; i < 5; i++) {
    const c = bloco10.slice(i * 2, i * 2 + 2);
    if (c && c !== '00') out.push({ codigo: c, descricao: RETORNO_MOTIVOS[c] || 'Desconhecido' });
  }
  return out;
}

function _parseSegT(l) {
  return {
    tipo: 'segmento_t',
    lote: _pint(l.slice(3, 7)),
    sequencial: _pint(l.slice(8, 13)),
    ocorrencia: l.slice(15, 17),
    ocorrencia_desc: RETORNO_OCORRENCIAS[l.slice(15, 17)] || 'Desconhecida',
    agencia: l.slice(17, 22),
    conta: l.slice(23, 35),
    nosso_numero: l.slice(37, 46).trim(),
    carteira: l.slice(57, 58),
    seu_numero: l.slice(58, 73).trim(),
    data_vencimento: _pdata(l.slice(73, 81)),
    valor_titulo_centavos: _pint(l.slice(81, 96)),
    banco_cobrador: l.slice(96, 99),
    agencia_cobradora: l.slice(99, 104),
    identificacao_titulo: l.slice(105, 130).trim(),
    tipo_inscricao_pagador: l.slice(130, 131),
    cpf_cnpj_pagador: l.slice(131, 146).replace(/^0+/, ''),
    nome_pagador: l.slice(146, 186).trim(),
    valor_tarifa_centavos: _pint(l.slice(198, 213)),
    motivos: _motivos(l.slice(213, 223)),
  };
}

function _parseSegU(l) {
  return {
    juros_multa_centavos: _pint(l.slice(17, 32)),
    desconto_concedido_centavos: _pint(l.slice(32, 47)),
    abatimento_concedido_centavos: _pint(l.slice(47, 62)),
    iof_recolhido_centavos: _pint(l.slice(62, 77)),
    valor_pago_centavos: _pint(l.slice(77, 92)),
    valor_liquido_centavos: _pint(l.slice(92, 107)),
    outras_despesas_centavos: _pint(l.slice(107, 122)),
    outros_creditos_centavos: _pint(l.slice(122, 137)),
    data_ocorrencia: _pdata(l.slice(137, 145)),
    data_credito: _pdata(l.slice(145, 153)),
  };
}

function parseRetorno(conteudo) {
  const linhas = conteudo.replace(/\r\n/g, '\n').split('\n').filter(l => l.length > 0);
  if (linhas.length === 0) throw new Error('Arquivo retorno vazio');
  const r = { header_arquivo: null, header_lote: null, trailer_lote: null,
              trailer_arquivo: null, eventos: [], erros_parse: [] };
  let ev = null;
  linhas.forEach((l, idx) => {
    if (l.length !== 240) {
      r.erros_parse.push('Linha ' + (idx + 1) + ': ' + l.length + ' chars');
      return;
    }
    const tr = l[7];
    if (tr === '0') {
      r.header_arquivo = {
        banco: l.slice(0, 3), cnpj: l.slice(18, 32),
        agencia: l.slice(52, 57), conta: l.slice(58, 70),
        razao_social: l.slice(72, 102).trim(),
        data_geracao: _pdata(l.slice(143, 151)),
      };
    } else if (tr === '1') {
      r.header_lote = { lote: _pint(l.slice(3, 7)), operacao: l[8] };
    } else if (tr === '3') {
      const seg = l[13];
      if (seg === 'T') {
        if (ev) r.eventos.push(ev);
        ev = _parseSegT(l);
      } else if (seg === 'U') {
        if (!ev) { r.erros_parse.push('Linha ' + (idx + 1) + ': U sem T'); return; }
        ev.valores = _parseSegU(l);
      }
    } else if (tr === '5') {
      if (ev) { r.eventos.push(ev); ev = null; }
      r.trailer_lote = {
        qtd_registros: _pint(l.slice(17, 23)),
        qtd_titulos: _pint(l.slice(23, 29)),
        valor_total_centavos: _pint(l.slice(29, 46)),
      };
    } else if (tr === '9') {
      r.trailer_arquivo = {
        qtd_lotes: _pint(l.slice(17, 23)),
        qtd_registros: _pint(l.slice(23, 29)),
      };
    }
  });
  if (ev) r.eventos.push(ev);
  return r;
}

function classificarEvento(ev) {
  const oc = ev.ocorrencia || '';
  let status = 'OUTRO';
  if (['02', '04'].includes(oc)) status = 'CONFIRMADO';
  else if (['03', '26', '30'].includes(oc)) status = 'REJEITADO';
  else if (['06', '08', '17', '46'].includes(oc)) status = 'LIQUIDADO';
  else if (['05', '09', '10', '25', '40'].includes(oc)) status = 'BAIXADO';
  else if (['07', '14', '27', '19', '20', '33', '34'].includes(oc)) status = 'ALTERADO';
  const v = ev.valores || {};
  return {
    nosso_numero: (ev.nosso_numero || '').replace(/^0+/, '') || '0',
    seu_numero: ev.seu_numero || '',
    ocorrencia: oc,
    ocorrencia_desc: ev.ocorrencia_desc || '',
    status,
    valor_titulo_centavos: ev.valor_titulo_centavos || 0,
    valor_pago_centavos: v.valor_pago_centavos || 0,
    valor_liquido_centavos: v.valor_liquido_centavos || 0,
    juros_multa_centavos: v.juros_multa_centavos || 0,
    desconto_centavos: v.desconto_concedido_centavos || 0,
    data_ocorrencia: v.data_ocorrencia || null,
    data_credito: v.data_credito || null,
    motivos_rejeicao: ev.motivos || [],
    pagador_nome: ev.nome_pagador || '',
    pagador_doc: ev.cpf_cnpj_pagador || '',
  };
}

// ---------- BOLETO: fator, DAC, DV, CB, LD ----------

const DATA_BASE_FATOR = new Date(Date.UTC(2022, 4, 29));  // 29/05/2022

function fatorVencimento(dataVenc) {
  let d = dataVenc;
  if (typeof d === 'string') d = new Date(d + 'T00:00:00Z');
  const delta = Math.floor((d - DATA_BASE_FATOR) / (1000 * 60 * 60 * 24));
  if (delta < 1000) throw new Error('vencimento anterior a 22/02/2025 - fator invalido no layout novo');
  if (delta > 9999) return ((delta - 1000) % 9000) + 1000;
  return delta;
}

function dacCodigoBarras(barras43) {
  if (barras43.length !== 43) throw new Error('barras43 tem ' + barras43.length + ' chars');
  const pesos = [2, 3, 4, 5, 6, 7, 8, 9];
  let soma = 0;
  const rev = barras43.split('').reverse();
  for (let i = 0; i < rev.length; i++) {
    soma += parseInt(rev[i], 10) * pesos[i % 8];
  }
  const resto = soma % 11;
  if (resto === 0 || resto === 1 || resto === 10) return '1';
  return String(11 - resto);
}

function dvModulo10(campo) {
  let soma = 0;
  let peso = 2;
  const rev = campo.split('').reverse();
  for (const ch of rev) {
    const produto = parseInt(ch, 10) * peso;
    soma += Math.floor(produto / 10) + (produto % 10);
    peso = peso === 2 ? 1 : 2;
  }
  const resto = soma % 10;
  return resto === 0 ? '0' : String(10 - resto);
}

function codigoBarras44(cfg, nossoNumero, dataVenc, valorCentavos) {
  const fator = fatorVencimento(dataVenc);
  const campoLivre = (
    cfg.SISTEMA_SAFRA +
    cfg.AGENCIA +
    cfg.CONTA_COMPLETA +
    String(nossoNumero).padStart(9, '0') +
    '2'  // Tipo Cobranca Registrada
  );
  if (campoLivre.length !== 25) throw new Error('campo_livre len=' + campoLivre.length);
  const valorStr = String(valorCentavos).padStart(10, '0');
  const barrasSemDac = (
    cfg.BANCO +
    '9' +
    String(fator).padStart(4, '0') +
    valorStr +
    campoLivre
  );
  if (barrasSemDac.length !== 43) throw new Error('barras sem dac len=' + barrasSemDac.length);
  const dac = dacCodigoBarras(barrasSemDac);
  return barrasSemDac.slice(0, 4) + dac + barrasSemDac.slice(4);
}

function linhaDigitavel(codBarras) {
  if (codBarras.length !== 44) throw new Error('cb len=' + codBarras.length);
  const banco = codBarras.slice(0, 3);
  const moeda = codBarras.slice(3, 4);
  const dac = codBarras.slice(4, 5);
  const fator = codBarras.slice(5, 9);
  const valor = codBarras.slice(9, 19);
  const cl = codBarras.slice(19, 44);
  const sistema = cl.slice(0, 1);
  const agencia = cl.slice(1, 6);
  const conta = cl.slice(6, 15);
  const nn = cl.slice(15, 24);
  const tipoCob = cl.slice(24, 25);
  const c1 = banco + moeda + sistema + agencia.slice(0, 4);
  const c1dv = dvModulo10(c1);
  const c2 = agencia.slice(4) + conta;
  const c2dv = dvModulo10(c2);
  const c3 = nn + tipoCob;
  const c3dv = dvModulo10(c3);
  const c5 = fator + valor;
  return (
    c1.slice(0, 5) + '.' + c1.slice(5) + c1dv + ' ' +
    c2.slice(0, 5) + '.' + c2.slice(5) + c2dv + ' ' +
    c3.slice(0, 5) + '.' + c3.slice(5) + c3dv + ' ' +
    dac + ' ' +
    c5
  );
}

// Exporta se rodar em Node standalone (pra teste), senao ignora
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    alfa, num, fmtData,
    headerArquivo, headerLote, segmentoP, segmentoQ, segmentoR,
    trailerLote, trailerArquivo, gerarRemessa,
    gerarRemessaEntrada, gerarRemessaBaixa, gerarRemessaAlteracaoVenc,
    gerarRemessaAlteracaoDados, gerarRemessaProtesto, gerarRemessaSustarProtesto,
    parseRetorno, classificarEvento,
    RETORNO_OCORRENCIAS, RETORNO_MOTIVOS,
    fatorVencimento, dacCodigoBarras, dvModulo10, codigoBarras44, linhaDigitavel,
  };
}
