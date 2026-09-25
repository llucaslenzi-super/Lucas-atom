
const r = ($input.first() && $input.first().json) || {};
const ctx = $('Prep').first().json.ctx;
const content = r.content || [];
let inp = {};
for(const c of content){ if(c && c.type==='tool_use'){ inp = c.input || {}; break; } }
const usageR = r.usage || {input_tokens:0, output_tokens:0};
const acaoIA = String(inp.acao || 'fora_escopo');
const perfil = ctx.perfil_efetivo || ctx.area || '';
const permiteRS = !!ctx.permite_rs;

// ---- tabelas permitidas por perfil (schema.tabela, minusculo) ----
const IND = ['nekt_raw.mssql_gaspar_dbo_produtos','nekt_raw.mssql_gaspar_dbo_estoque_nr_peca','nekt_raw.mssql_gaspar_dbo_estoque_local','nekt_raw.mssql_gaspar_dbo_estoque_local_lote_fios','nekt_raw.mssql_gaspar_dbo_movimentos_estoque','nekt_raw.mssql_gaspar_dbo_grade_produtos','nekt_raw.mssql_gaspar_dbo_ficha_tecnica_produtos_composicao','nekt_raw.mssql_gaspar_dbo_pedidos_venda_capa','nekt_raw.mssql_gaspar_dbo_pedidos_venda_itens','nekt_raw.mssql_gaspar_dbo_op_tecelagem','nekt_raw.mssql_gaspar_dbo_op_tecelagem_entrada_fios','nekt_raw.mssql_gaspar_dbo_op_tint_capa','nekt_raw.mssql_gaspar_dbo_op_tint_item','nekt_raw.mssql_gaspar_dbo_op_tint_item_pecas','nekt_raw.mssql_gaspar_dbo_op_tint_item_pecas_separadas','nekt_raw.mssql_gaspar_dbo_op_tint_item_pedidos','nekt_raw.mssql_gaspar_dbo_fatura_capa','nekt_raw.mssql_gaspar_dbo_fatura_itens','nekt_raw.mssql_gaspar_dbo_clientes'];
const FIN = ['nekt_service.faturas_unificadas_completo','nekt_raw.mssql_gaspar_dbo_cr_documentos','nekt_raw.mssql_gaspar_dbo_cp_documentos','nekt_raw.mssql_gaspar_dbo_cr_lancamentos','nekt_raw.mssql_gaspar_dbo_cp_lancamentos','nekt_raw.mssql_gaspar_dbo_credito_cliente','nekt_raw.mssql_gaspar_dbo_despesas','nekt_raw.mssql_gaspar_dbo_despesas_subgrupos','nekt_raw.mssql_gaspar_dbo_cp_documentos_despesas','nekt_raw.mssql_gaspar_dbo_cp_documentos_centro_custo_conta_contabil','nekt_raw.mssql_gaspar_dbo_cp_documentos_tributos','nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr','nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr_lancto_cp','nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr_lancto_cr','nekt_raw.mssql_gaspar_dbo_nota_fiscal_capa','nekt_raw.mssql_gaspar_dbo_nota_fiscal_eletronica_eventos','nekt_raw.mssql_gaspar_dbo_entradas_itens_lancamentos_saldos','nekt_raw.mssql_gaspar_dbo_cad_tear','nekt_raw.mssql_gaspar_dbo_clientes','nekt_raw.mssql_gaspar_dbo_fornecedores'];
let allowed = null; // null = qualquer tabela (Diretoria)
if(perfil==='Diretoria'){ allowed = null; }
else if(perfil==='Financeiro' || perfil==='Comercial'){ allowed = FIN; }
else if(perfil==='Industrial' || perfil==='Qualidade'){ allowed = IND; }
else { allowed = []; }

const MONEY = /\b(valor[a-z_]*|vlr[a-z_]*|preco[a-z_]*|custo[a-z_]*|saldo[a-z_]*|precounit[a-z_]*)\b/i;
const BAD = /\b(insert|update|delete|drop|alter|create|truncate|merge|grant|revoke|describe|comment|analyze|explain)\b/i;

function validar(sqlIn){
  let s = String(sqlIn||'').trim();
  if(!s) return { ok:false, motivo:'vazio' };
  s = s.replace(/;+\s*$/,'').trim();
  if(s.indexOf(';') >= 0) return { ok:false, motivo:'multiplos_comandos' };
  if(/\/\*/.test(s) || /--/.test(s)) return { ok:false, motivo:'comentario' };
  if(!/^(select|with)\b/i.test(s)) return { ok:false, motivo:'nao_select' };
  if(BAD.test(s)) return { ok:false, motivo:'palavra_proibida' };
  // tabelas referenciadas
  const refs = []; const re=/\b(?:from|join)\s+([a-zA-Z_][\w]*\.[a-zA-Z_][\w]*)/gi; let m;
  while((m=re.exec(s))){ refs.push(m[1].toLowerCase()); }
  for(const t of refs){ const sc=t.split('.')[0]; if(['nekt_raw','nekt_service','nekt_trusted'].indexOf(sc) < 0) return { ok:false, motivo:'schema_nao_permitido:'+t }; }
  if(allowed !== null){ for(const t of refs){ if(allowed.indexOf(t) < 0) return { ok:false, motivo:'tabela_fora_perfil' }; } }
  // Industrial/Qualidade: bloqueia colunas monetarias
  if(!permiteRS && MONEY.test(s)) return { ok:false, motivo:'r$' };
  // garante LIMIT
  if(!/\blimit\s+\d+/i.test(s)) s = s + ' LIMIT 200';
  if(s.length > 6000) return { ok:false, motivo:'muito_longa' };
  return { ok:true, sql:s };
}

let acao='fora'; let sql=''; let fonte=String(inp.fonte||''); let answerObj=null; let respostaFixa='';

if(acaoIA==='sql'){
  const v = validar(inp.sql);
  if(v.ok){ acao='tool'; sql=v.sql; if(!fonte) fonte='ERP Soul (Nekt)'; }
  else if(v.motivo==='r$'){ acao='fora'; respostaFixa='Seu perfil ('+(ctx.area||perfil)+') acompanha os indicadores em kg, pecas e percentuais — valores em R$ ficam com os perfis Financeiro e Diretoria. Posso trazer esses mesmos dados em volume (kg/pecas). Deseja?'; }
  else if(v.motivo && v.motivo.indexOf('tabela_fora_perfil')===0){ acao='fora'; const mapa={ Industrial:'estoque, producao, PCP, fios, pedidos e qualidade (kg e %)', Qualidade:'estoque, producao e qualidade (kg e %)', Financeiro:'faturamento, contas a pagar/receber, titulos e despesas (R$ e kg)', Comercial:'faturamento, produtos, clientes e pedidos', Diretoria:'todas as areas' }; respostaFixa='Essa consulta esta fora do seu perfil de acesso ('+(ctx.area||perfil)+'). Seu perfil consulta: '+(mapa[perfil]||'as fontes autorizadas pelo Comite de IA')+'. Se precisar desse dado, solicite acesso pela tela de Configuracoes.'; }
  else { acao='fora'; respostaFixa='Nao consegui montar a consulta para essa pergunta. Tente reformular com mais detalhes (produto, periodo, filial, etc.).'; }
} else if(acaoIA==='conversa'){
  acao='geral';
  answerObj = { model:ctx.modelo, max_tokens:800, system:'Voce e o assistente de IA da Soul Textil, perfil '+(ctx.area||perfil)+'. Seja cordial e objetivo. Voce consulta o ERP da Soul (estoque, producao, faturamento, financeiro conforme o perfil). Pode explicar o que consegue consultar, mas NAO invente dados reais; para dados reais, o usuario deve perguntar diretamente. '+(permiteRS?'':'Nunca exponha valores em R$ para este perfil.'), messages:[{ role:'user', content: ctx.mensagem }] };
} else {
  acao='fora';
  const mapa={ Industrial:'estoque, producao, PCP, fios, pedidos e qualidade (kg e %)', Qualidade:'estoque, producao e qualidade (kg e %)', Financeiro:'faturamento, contas a pagar/receber, titulos e despesas (R$ e kg)', Comercial:'faturamento, produtos, clientes e pedidos', Diretoria:'todas as areas' };
  respostaFixa = String(inp.motivo||'').slice(0,240) ? ('Essa consulta esta fora do seu perfil de acesso ('+(ctx.area||perfil)+'). Seu perfil consulta: '+(mapa[perfil]||'as fontes autorizadas pelo Comite de IA')+'.') : ('Essa consulta esta fora do seu perfil de acesso ('+(ctx.area||perfil)+').');
}

const nektObj = sql ? { sql:sql, mode:'csv', mode_options:{ header:true, delimiter:',' } } : null;
return [{ json:{ acao:acao, ferramenta:acaoIA, fonte:fonte, sql_gerado:sql, nektBody:(nektObj?JSON.stringify(nektObj):''), answerBody:(answerObj?JSON.stringify(answerObj):''), respostaFixa:respostaFixa, router_in:(usageR.input_tokens||0), router_out:(usageR.output_tokens||0) } }];
