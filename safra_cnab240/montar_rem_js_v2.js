
const CFG = {
  BANCO: '422',
  AGENCIA: '02900',
  CONTA_NUMERO: '00587521',
  CONTA_DV: '6',
  CONTA_COMPLETA: '005875216',
  CNPJ: '35588873000141',
  RAZAO_SOCIAL: 'SOUL INDUSTRIA DE TECIDOS LTDA',
  CARTEIRA: '1',
  LAYOUT_VERSAO_ARQUIVO: '103',
  LAYOUT_VERSAO_LOTE: '060',
  CADASTRO_TITULO: '1',
  TIPO_DOCUMENTO: '2',
  IDENTIFICACAO_BLOQUETO: '2',
  DISTRIBUICAO_BLOQUETO: '2',
  SISTEMA_SAFRA: '7'
};
function alfa(v, tam){ const s=(v==null?'':String(v)).toUpperCase(); return s.slice(0,tam).padEnd(tam,' '); }
function num(v, tam){ const s=v==null?'':String(v); return s.slice(-tam).padStart(tam,'0'); }
function fmtData(d){ let x=d; if(typeof d==='string') x=new Date(d+'T00:00:00Z'); if(!(x instanceof Date)||isNaN(x)) throw new Error('data invalida:'+d); return String(x.getUTCDate()).padStart(2,'0')+String(x.getUTCMonth()+1).padStart(2,'0')+String(x.getUTCFullYear()); }
function assertLen(l, t){ if(l.length!==240) throw new Error(t+':'+l.length); return l; }

function headerArquivo(seqArquivo, dataGeracao){
  return assertLen([
    num(CFG.BANCO,3), num('0',4), num('0',1), alfa('',9), num('2',1), num(CFG.CNPJ,14),
    alfa('',20), num(CFG.AGENCIA,5), alfa('',1), num(CFG.CONTA_NUMERO,12), alfa(CFG.CONTA_DV,1),
    alfa('',1), alfa(CFG.RAZAO_SOCIAL,30), alfa('BANCO SAFRA S/A',30), alfa('',10), num('1',1),
    num(fmtData(dataGeracao),8), num('0',6), num(seqArquivo,6), num(CFG.LAYOUT_VERSAO_ARQUIVO,3),
    alfa('',5), alfa('',20), alfa('',20), alfa('',29)
  ].join(''),'HA');
}
function headerLote(numeroLote, dataGeracao){
  return assertLen([
    num(CFG.BANCO,3), num(numeroLote,4), num('1',1), alfa('R',1), num('01',2), alfa('',2),
    num(CFG.LAYOUT_VERSAO_LOTE,3), alfa('',1), num('2',1), num(CFG.CNPJ,15), alfa('',20),
    num(CFG.AGENCIA,5), alfa('',1), num(CFG.CONTA_NUMERO,12), alfa(CFG.CONTA_DV,1), alfa('',1),
    alfa(CFG.RAZAO_SOCIAL,30), alfa('',40), alfa('',40), num('1',8), num(fmtData(dataGeracao),8),
    num('0',8), alfa('',33)
  ].join(''),'HL');
}
function segmentoP(numeroLote, seq, t, codMov){
  const nnField = num(t.nosso_numero,9) + alfa('',11);
  // Regra Safra: cod juros=3 (isento) forca data=0 e valor=0
  let jurosDataStr, jurosValor;
  if (t.juros_codigo === '3') { jurosDataStr = '00000000'; jurosValor = 0; }
  else { jurosDataStr = fmtData(t.juros_data); jurosValor = t.juros_valor_centavos; }
  // desconto codigo 0 = sem desconto -> data e valor zerados
  let descDataStr, descValor;
  if (t.desconto_codigo === '0') { descDataStr = '00000000'; descValor = 0; }
  else { descDataStr = fmtData(t.desconto_data); descValor = t.desconto_valor_centavos; }
  return assertLen([
    num(CFG.BANCO,3), num(numeroLote,4), num('3',1), num(seq,5), alfa('P',1), alfa('',1),
    num(codMov,2), num(CFG.AGENCIA,5), alfa('',1), num(CFG.CONTA_NUMERO,12), alfa(CFG.CONTA_DV,1),
    alfa('',1), nnField, num(CFG.CARTEIRA,1), num(CFG.CADASTRO_TITULO,1), alfa(CFG.TIPO_DOCUMENTO,1),
    num(CFG.IDENTIFICACAO_BLOQUETO,1), alfa(CFG.DISTRIBUICAO_BLOQUETO,1), alfa(t.seu_numero,15),
    num(fmtData(t.data_vencimento),8), num(t.valor_centavos,15), num(CFG.AGENCIA,5), alfa('',1),
    num(t.especie,2), alfa('N',1), num(fmtData(t.data_emissao),8), num(t.juros_codigo,1),
    num(jurosDataStr,8), num(jurosValor,15), num(t.desconto_codigo,1),
    num(descDataStr,8), num(descValor,15), num('0',15), num('0',15),
    alfa(t.seu_numero,25), num(t.protesto_codigo,1), num(t.protesto_dias,2), num(t.baixa_codigo,1),
    alfa(num(t.baixa_dias,3),3), num('09',2), num('0',10), alfa('1',1)
  ].join(''),'P');
}
function segmentoQ(numeroLote, seq, t, codMov){
  const p = t.pagador;
  return assertLen([
    num(CFG.BANCO,3), num(numeroLote,4), num('3',1), num(seq,5), alfa('Q',1), alfa('',1),
    num(codMov,2), num(p.tipo_inscricao,1), num(p.cpf_cnpj,15), alfa(p.nome,40),
    alfa(p.endereco,40), alfa(p.bairro,15), num(p.cep_prefixo,5), num(p.cep_sufixo,3),
    alfa(p.cidade,15), alfa(p.uf,2), num('0',1), num('0',15), alfa('',40),
    num('0',3), alfa('',20), alfa('',8)
  ].join(''),'Q');
}
function trailerLote(numeroLote, qtdReg, qtdTit, valorTot){
  return assertLen([
    num(CFG.BANCO,3), num(numeroLote,4), num('5',1), alfa('',9), num(qtdReg,6), num(qtdTit,6),
    num(valorTot,17), num('0',6), num('0',17), num('0',6), num('0',17), num('0',6), num('0',17),
    alfa('',8), alfa('',117)
  ].join(''),'TL');
}
function trailerArquivo(qtdLotes, qtdReg){
  return assertLen([
    num(CFG.BANCO,3), num('9999',4), num('9',1), alfa('',9), num(qtdLotes,6), num(qtdReg,6),
    num('0',6), alfa('',205)
  ].join(''),'TA');
}

const rows = $input.all().map(i => i.json).filter(r => r && r.payload_json && r.codigo_movimento);
if (rows.length === 0) {
  return [{ json: { tem_rem: false, motivo: 'fila_vazia', qtd: 0, valor_total_centavos: 0, conteudo_rem: '' } }];
}

const hoje = new Date();
const seqArquivo = 1;
const numeroLote = 1;

const linhas = [];
linhas.push(headerArquivo(seqArquivo, hoje));
linhas.push(headerLote(numeroLote, hoje));

let seq = 0;
let valorTotal = 0;
let qtdTitulos = 0;
const idsProcessados = [];
const nossosNumerosProcessados = [];

for (const r of rows) {
  let titulo;
  try { titulo = JSON.parse(r.payload_json); } catch(e) { continue; }
  if (!titulo.nosso_numero) titulo.nosso_numero = r.nosso_numero;
  seq++;
  linhas.push(segmentoP(numeroLote, seq, titulo, r.codigo_movimento));
  seq++;
  linhas.push(segmentoQ(numeroLote, seq, titulo, r.codigo_movimento));
  valorTotal += Number(titulo.valor_centavos || 0);
  qtdTitulos++;
  if (r.id) idsProcessados.push(r.id);
  nossosNumerosProcessados.push(r.nosso_numero);
}

const qtdRegDetalhe = 2 * qtdTitulos;
const qtdRegLote = qtdRegDetalhe + 2;
linhas.push(trailerLote(numeroLote, qtdRegLote, qtdTitulos, valorTotal));
const qtdRegArquivo = linhas.length + 1;
linhas.push(trailerArquivo(1, qtdRegArquivo));

const conteudo = linhas.join('\r\n') + '\r\n';

return [{
  json: {
    tem_rem: true,
    qtd: qtdTitulos,
    valor_total_centavos: valorTotal,
    valor_total_reais: (valorTotal / 100).toFixed(2),
    sequencial_arquivo: seqArquivo,
    conteudo_rem: conteudo,
    data_geracao: hoje.toISOString(),
    ids_processados: idsProcessados,
    nossos_numeros: nossosNumerosProcessados,
    tamanho_bytes: conteudo.length,
    linhas: linhas.length
  }
}];
