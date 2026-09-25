
const crypto = require('crypto');
const req = $('Webhook Chat').first().json;
const headers = req.headers || {};
const body = req.body || {};
const auth = String(headers.authorization || headers.Authorization || '');
const token = (auth.toLowerCase().indexOf('bearer ') === 0 ? auth.slice(7).trim() : auth.trim());
const sr = $('Get HMAC Chat').first();
const secret = (sr && sr.json.valor) || '';
function toBuf(s){ const t = s.replace(/-/g,'+').replace(/_/g,'/'); const pad = (4 - (t.length % 4)) % 4; return Buffer.from(t + '='.repeat(pad), 'base64'); }
function fail(code, erro){ return [{json:{ valido:false, statusCode:code, body:{ sucesso:false, erro } }}]; }
if(!secret) return fail(500,'sem_config');
if(!token) return fail(401,'sem_token');
const parts = token.split('.');
if(parts.length !== 2) return fail(401,'token_invalido');
const expected = crypto.createHmac('sha256', secret).update(parts[0]).digest();
let provided; try { provided = toBuf(parts[1]); } catch(e){ return fail(401,'assinatura_invalida'); }
if(expected.length !== provided.length || !crypto.timingSafeEqual(expected, provided)) return fail(401,'assinatura_invalida');
let payload; try { payload = JSON.parse(toBuf(parts[0]).toString('utf8')); } catch(e){ return fail(401,'payload_invalido'); }
if(!payload.exp || new Date(payload.exp).getTime() < Date.now()) return fail(401,'expirado');
const area = payload.area || '';
const is_admin = !!payload.is_admin;
const modelosOk = ['claude-opus-5-5','claude-sonnet-5','claude-haiku-4-5-20251001'];
const modelo = modelosOk.indexOf(String(body.modelo||'')) >= 0 ? String(body.modelo) : 'claude-sonnet-5';
const mensagemRaw = String(body.mensagem || '').slice(0, 4000);
let msg = mensagemRaw;
const guardrails = [];
let b1 = msg; msg = msg.replace(/\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}/g,'[CNPJ]'); if(msg!==b1) guardrails.push('cnpj_mascarado');
let b2 = msg; msg = msg.replace(/\d{3}\.?\d{3}\.?\d{3}-?\d{2}/g,'[CPF]'); if(msg!==b2) guardrails.push('cpf_mascarado');
let b3 = msg; msg = msg.replace(/\(?\d{2}\)?\s?9?\d{4}-?\d{4}/g,'[TELEFONE]'); if(msg!==b3) guardrails.push('telefone_mascarado');
const alerta = guardrails.length ? 'pii' : '';
function ymd(d){ return d.toISOString().slice(0,10); }
const hoje = ymd(new Date());

// ---- Escopo do perfil: R$ permitido? e catalogo de tabelas ----
// area normalizada: Diretoria/admin = tudo; Comercial = vendas (R$); Qualidade = industrial (sem R$)
const perfilEfetivo = is_admin ? 'Diretoria' : (area || '');
const permiteRS = (perfilEfetivo==='Diretoria' || perfilEfetivo==='Financeiro' || perfilEfetivo==='Comercial');

const CAT_IND = [
'nekt_raw.mssql_gaspar_dbo_produtos: codproduto, descricao, unidade, codgrupo, codsubgrupo, composicao, largramada, gramramada, tecido, titulone, tipofio, codprodutocru, ativo -- cadastro de produtos/tecidos',
'nekt_raw.mssql_gaspar_dbo_estoque_nr_peca: nrpeca, codproduto, qtdekg, qtdepc, qualidade, situacao(1=disponivel), codlocal, nrpedido(0/null=livre), revisao(1=peca atual), nroptint, nroptecelagem, datainclusao, localizacao -- estoque de pecas/rolos acabados (kg e pecas)',
'nekt_raw.mssql_gaspar_dbo_estoque_local: codproduto, codlocal, estoque, reserva -- saldo de estoque por local',
'nekt_raw.mssql_gaspar_dbo_estoque_local_lote_fios: codproduto, codlocal, lote, estoque, caixas -- estoque de fios por lote',
'nekt_raw.mssql_gaspar_dbo_movimentos_estoque: sequencia, codproduto, data, codlocal, transacao, movimento, quantidade, quantidadepcs, nrop, nroptecelagem -- movimentacoes de estoque',
'nekt_raw.mssql_gaspar_dbo_grade_produtos: codgrade, descricao, composicao, pantone, listadefibras -- cores/grades',
'nekt_raw.mssql_gaspar_dbo_ficha_tecnica_produtos_composicao: codproduto, codprodutocomposicao, percentualcomposicao -- composicao % (materia-prima/fios) do produto',
'nekt_raw.mssql_gaspar_dbo_pedidos_venda_capa: nrpedido, codcliente, dataemissao, dataentrega, status, codvendedor, codrepresentante -- pedidos de venda (cabecalho)',
'nekt_raw.mssql_gaspar_dbo_pedidos_venda_itens: nrpedido, linha, codproduto, codgrade, quantidade, quantidadepc, qtdefaturada, qtdefaturadapc, qtdeseparada, status_item -- itens de pedido (qtd/kg e pecas)',
'nekt_raw.mssql_gaspar_dbo_op_tecelagem: nroptecelagem, dataemissao, nrpecas, status, codproduto, pesototal, pesoproduzido, pecasproduzidas, codtear, codlocal, dataentregapedido -- OP de tecelagem (kg produzidos)',
'nekt_raw.mssql_gaspar_dbo_op_tecelagem_entrada_fios: nroptecelagem, linha, codproduto, quantidade, percfio, quantidadeconsumida, lote -- consumo de fios na tecelagem',
'nekt_raw.mssql_gaspar_dbo_op_tint_capa: nroptint, codfornecedor, dataemissao, dataentrega, status, tipoprocesso -- OP de tinturaria (cabecalho)',
'nekt_raw.mssql_gaspar_dbo_op_tint_item: nroptint, nroptintitem, codprodutocru, codprodutoaca, qtdekg, qtdepc, qtdekgret, qtdepcret, dataretorno, codgrade, codcliente -- itens de tinturaria (kg enviado/retornado)',
'nekt_raw.mssql_gaspar_dbo_op_tint_item_pecas: nroptint, nroptintitem, nrpeca, peso, npecas, codproduto -- pecas por item de tinturaria',
'nekt_raw.mssql_gaspar_dbo_op_tint_item_pedidos: nroptint, nroptintitem, nrpedido, linha, quantidade, quantidadepc -- vinculo tinturaria<->pedido',
'nekt_raw.mssql_gaspar_dbo_fatura_itens: nrfatura, item, codproduto, descproduto, quantidade, unidade, quantidadekg, quantidadepc, nrpedido, codgrade -- itens faturados (para Industrial use SOMENTE quantidades)',
'nekt_raw.mssql_gaspar_dbo_fatura_capa: nrfatura, dataemissao, codcliente, nomecliente, codrepresentante, quantidadevolumes -- cabecalho de fatura (para Industrial use SOMENTE datas/cliente/quantidades)',
'nekt_raw.mssql_gaspar_dbo_clientes: codcliente, nome, fantasia, cidade, estado, codrepresentante, ativo -- cliente (use apenas nome/fantasia/cidade)'
].join('\n');

const CAT_FIN = [
'nekt_service.faturas_unificadas_completo: origem(GASPAR/LOJASP/MATRIZ), dataemissao, nrfatura, item, codproduto, descproduto, quantidadekg, quantidadepc, precounitario, vlrtotalitem, nrpedido, codgrade, descgrade, codlocal, codcliente, nome, fantasia, cidade, estado -- faturamento consolidado das 3 filiais; o NOME do cliente esta na coluna nome (NAO existe nomecliente); use para faturamento/vendas por periodo, por produto ou por cliente',
'nekt_raw.mssql_gaspar_dbo_cr_documentos: codcliente, tipodocumento, documento, parcela, datavencimento, datalancamento, dataemissao, dataquitacao, valordocumento, saldodocumento, codportador, documentoorigem -- contas a receber (saldodocumento>0 = em aberto; vencido = datavencimento<current_date)',
'nekt_raw.mssql_gaspar_dbo_cp_documentos: codfornecedor, tipodocumento, documento, parcela, datavencimento, datalancamento, dataemissao, dataquitacao, valordocumento, saldodocumento, coddespesa, numerobordero -- contas a pagar',
'nekt_raw.mssql_gaspar_dbo_cr_lancamentos: codcliente, tipodocumento, documento, parcela, datalancamento, valor, historico, tipodc, codcentrocusto, codcontacontabil -- lancamentos/baixas a receber',
'nekt_raw.mssql_gaspar_dbo_cp_lancamentos: codfornecedor, datalancamento, documento, tipodocumento, valor, tipolancamento, tipodc, codcentrocusto, codcontacontabil, coddespesa -- lancamentos a pagar',
'nekt_raw.mssql_gaspar_dbo_credito_cliente: codcliente, datalancamento, valor, historico, tipolancamento -- creditos de cliente',
'nekt_raw.mssql_gaspar_dbo_despesas: coddespesa, descricao, grupodespesa, codigo_subgrupo -- plano de despesas',
'nekt_raw.mssql_gaspar_dbo_despesas_subgrupos: codigo_subgrupo, descricao -- subgrupos de despesa',
'nekt_raw.mssql_gaspar_dbo_cp_documentos_despesas: codfornecedor, tipodocumento, documento, parcela, coddespesa, valor -- rateio de CP por despesa',
'nekt_raw.mssql_gaspar_dbo_cp_documentos_centro_custo_conta_contabil: codfornecedor, tipodocumento, documento, parcela, codcentrocusto, codcontacontabil, valor -- rateio de CP por centro de custo',
'nekt_raw.mssql_gaspar_dbo_cp_documentos_tributos: nrap, receita, valorprincipal_darf, datadevencimento_darf, competencia_gps, valordotributo_gps -- tributos de CP',
'nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr: bordero, valor, datalancamento, usuario -- compensacoes CP x CR',
'nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr_lancto_cp: bordero, codfornecedor, tipodocumento, documento, parcela, valorbaixa -- itens CP da compensacao',
'nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr_lancto_cr: bordero, codcliente, tipodocumento, documento, parcela, valorbaixa, valorjuros -- itens CR da compensacao',
'nekt_raw.mssql_gaspar_dbo_nota_fiscal_capa: referencia, entradasaida(E/S), numeronota, dataemissao, nome, valortotalprodutos, valortotalnota, valortotalipi, valoricms, municipio, uf -- notas fiscais (nao selecione cnpjcpf)',
'nekt_raw.mssql_gaspar_dbo_nota_fiscal_eletronica_eventos: entradasaida, referencia, codevento, nomeevento, dataregistroevento -- eventos NF-e',
'nekt_raw.mssql_gaspar_dbo_entradas_itens_lancamentos_saldos: referencia, linha, tipo, sequencia, data, quantidade, quantidadepc -- saldos de entradas',
'nekt_raw.mssql_gaspar_dbo_cad_tear: codtear, descricao, diametro, finura, ativo, codgrupo, marca, ano -- cadastro de teares',
'nekt_raw.mssql_gaspar_dbo_clientes: codcliente, nome, fantasia, cidade, estado -- cliente (nunca cnpjcpf/telefone/email)',
'nekt_raw.mssql_gaspar_dbo_fornecedores: codfornecedor, nome, fantasia, cidade, estado -- fornecedor (nunca cnpjcpf)'
].join('\n');

let catalogo, escopoTxt;
if(perfilEfetivo==='Diretoria'){
  catalogo = 'CATALOGO INDUSTRIAL (kg/pecas/%):\n'+CAT_IND+'\n\nCATALOGO FINANCEIRO (R$ e kg):\n'+CAT_FIN+'\n\nDiretoria tambem pode consultar qualquer outra tabela dos schemas nekt_raw, nekt_service e nekt_trusted (peca apenas colunas que existam).';
  escopoTxt = 'Perfil DIRETORIA: acesso total a todas as areas. Valores em R$ permitidos.';
} else if(perfilEfetivo==='Financeiro' || perfilEfetivo==='Comercial'){
  catalogo = 'CATALOGO FINANCEIRO/COMERCIAL (R$ e kg):\n'+CAT_FIN;
  escopoTxt = 'Perfil '+perfilEfetivo+': faturamento, contas a pagar/receber, titulos, notas fiscais e despesas. Valores em R$ permitidos. Nunca exponha cnpj/cpf/telefone/email.';
} else if(perfilEfetivo==='Industrial' || perfilEfetivo==='Qualidade'){
  catalogo = 'CATALOGO INDUSTRIAL (SOMENTE kg, pecas e %):\n'+CAT_IND;
  escopoTxt = 'Perfil '+perfilEfetivo+': estoque, producao (tecelagem/tinturaria), PCP, fios, pedidos e qualidade. Responda SEMPRE em kg, pecas e percentuais e NUNCA em R$ (nao selecione colunas de valor/preco/custo/saldo). Se a pergunta for sobre R$/faturamento em reais/preco, use acao=fora_escopo.';
} else {
  catalogo = '';
  escopoTxt = 'Perfil sem catalogo de dados atribuido. Use acao=fora_escopo para pedidos de dados.';
}

const regrasSQL = [
'MOTOR: Amazon Athena (Trino/Presto). Referencie tabelas como schema.tabela.',
'- Apenas SELECT (nunca INSERT/UPDATE/DELETE/DDL); uma unica instrucao; sem comentarios (-- ou /* */).',
'- Datas: DATE \'2026-01-31\'; hoje = current_date; intervalos = date_add(\'day\', -30, current_date); use DATE(coluna) para converter.',
'- Texto: lower(x), x LIKE \'%termo%\', TRIM(x), SPLIT_PART(x,\'#\',1). O nome limpo do produto = TRIM(SPLIT_PART(descricao,\'#\',1)).',
'- Numeros: SUM/COUNT/AVG; formate com CAST(x AS DECIMAL(16,2)).',
'- Em JOIN converta as chaves para texto: CAST(a.codproduto AS VARCHAR)=CAST(b.codproduto AS VARCHAR).',
'- Estoque de pecas acabadas: use estoque_nr_peca com situacao=1 AND revisao=1 AND codlocal IN (1,55).',
'- SEMPRE inclua LIMIT (<=200), exceto em agregacao que retorna 1 linha.',
'- Filiais (coluna origem): GASPAR=Gaspar/SC, LOJASP=Filial SP, MATRIZ=Filial PE.'
].join('\n');

const exemplos = [
'EXEMPLOS:',
'Pergunta: "estoque do tecido piquet"',
'SQL: SELECT TRIM(SPLIT_PART(p.descricao,\'#\',1)) produto, CAST(SUM(e.qtdekg) AS DECIMAL(14,2)) kg, SUM(e.qtdepc) pecas FROM nekt_raw.mssql_gaspar_dbo_estoque_nr_peca e JOIN nekt_raw.mssql_gaspar_dbo_produtos p ON CAST(p.codproduto AS VARCHAR)=CAST(e.codproduto AS VARCHAR) WHERE lower(p.descricao) LIKE \'%piquet%\' AND e.situacao=1 AND e.revisao=1 AND e.codlocal IN (1,55) GROUP BY 1 ORDER BY kg DESC LIMIT 20',
'Pergunta: "faturamento dos ultimos 30 dias" (Financeiro/Diretoria)',
'SQL: SELECT origem, CAST(SUM(vlrtotalitem) AS DECIMAL(16,2)) valor_rs, CAST(SUM(quantidadekg) AS DECIMAL(16,2)) kg, COUNT(DISTINCT nrfatura) faturas FROM nekt_service.faturas_unificadas_completo WHERE DATE(dataemissao) >= date_add(\'day\',-30,current_date) GROUP BY origem ORDER BY valor_rs DESC',
'Pergunta: "titulos vencidos" (Financeiro/Diretoria)',
'SQL: SELECT c.nome cliente, d.documento, CAST(DATE(d.datavencimento) AS VARCHAR) vencimento, CAST(d.saldodocumento AS DECIMAL(14,2)) saldo_rs FROM nekt_raw.mssql_gaspar_dbo_cr_documentos d LEFT JOIN nekt_raw.mssql_gaspar_dbo_clientes c ON CAST(c.codcliente AS VARCHAR)=CAST(d.codcliente AS VARCHAR) WHERE d.saldodocumento>0 AND DATE(d.datavencimento)<current_date ORDER BY d.datavencimento LIMIT 50'
].join('\n');

const sysPlanner = 'Voce e o agente de dados da Plataforma Soul (Soul Textil), um sistema de BI conversacional sobre o ERP (data warehouse Nekt). Hoje e '+hoje+'. '+escopoTxt+'\n\nSua tarefa: para a pergunta do usuario, escolha uma acao:\n- acao="sql": gere UMA consulta SQL (SELECT) sobre as tabelas do CATALOGO abaixo para responder a pergunta. Prefira SEMPRE isto quando a pergunta puder ser respondida com os dados do catalogo.\n- acao="conversa": saudacoes, ajuda, ou perguntas que nao pedem dados do ERP (ex.: "o que voce consegue consultar?").\n- acao="fora_escopo": a pergunta pede dados que NAO estao no catalogo/perfil (inclui Industrial pedindo valores em R$).\nPreencha "fonte" com um rotulo curto em portugues do que esta sendo consultado (ex.: "ERP - Estoque de tecidos (kg)").\n\n'+regrasSQL+'\n\n'+exemplos+'\n\n'+catalogo;

const plannerObj = { model:'claude-sonnet-5', max_tokens:1500, system: sysPlanner, tools:[{ name:'plano', description:'Planeja a resposta: gera SQL SELECT ou classifica a intencao.', input_schema:{ type:'object', properties:{ acao:{ type:'string', enum:['sql','conversa','fora_escopo'] }, sql:{ type:'string', description:'Consulta SQL SELECT (Athena/Trino) quando acao=sql' }, fonte:{ type:'string', description:'Rotulo curto do que esta sendo consultado' }, motivo:{ type:'string' } }, required:['acao'] } }], tool_choice:{ type:'tool', name:'plano' }, messages:[{ role:'user', content: msg }] };

const ctx = { usuario:payload.usuario, nome:payload.nome, perfil:payload.perfil, nivel:payload.nivel, area:area, perfil_efetivo:perfilEfetivo, permite_rs:permiteRS, is_admin:is_admin, modelo:modelo, mensagem:msg, mensagem_raw:mensagemRaw, guardrails:guardrails, alerta:alerta, ip:String(headers['x-forwarded-for']||''), dispositivo:String(headers['user-agent']||''), conversa_id: (String(body.conversa_id||'') || ('c-'+crypto.randomUUID())) };
return [{ json:{ valido:true, statusCode:200, ctx:ctx, routerBody: JSON.stringify(plannerObj) } }];
