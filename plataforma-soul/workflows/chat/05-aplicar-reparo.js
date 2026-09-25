
const r = ($input.first() && $input.first().json) || {};
const ctx = $('Prep').first().json.ctx;
const content = r.content || [];
let inp = {};
for(const c of content){ if(c && c.type==='tool_use'){ inp = c.input || {}; break; } }
const perfil = ctx.perfil_efetivo || ctx.area || '';
const permiteRS = !!ctx.permite_rs;
const IND = ['nekt_raw.mssql_gaspar_dbo_produtos','nekt_raw.mssql_gaspar_dbo_estoque_nr_peca','nekt_raw.mssql_gaspar_dbo_estoque_local','nekt_raw.mssql_gaspar_dbo_estoque_local_lote_fios','nekt_raw.mssql_gaspar_dbo_movimentos_estoque','nekt_raw.mssql_gaspar_dbo_grade_produtos','nekt_raw.mssql_gaspar_dbo_ficha_tecnica_produtos_composicao','nekt_raw.mssql_gaspar_dbo_pedidos_venda_capa','nekt_raw.mssql_gaspar_dbo_pedidos_venda_itens','nekt_raw.mssql_gaspar_dbo_op_tecelagem','nekt_raw.mssql_gaspar_dbo_op_tecelagem_entrada_fios','nekt_raw.mssql_gaspar_dbo_op_tint_capa','nekt_raw.mssql_gaspar_dbo_op_tint_item','nekt_raw.mssql_gaspar_dbo_op_tint_item_pecas','nekt_raw.mssql_gaspar_dbo_op_tint_item_pecas_separadas','nekt_raw.mssql_gaspar_dbo_op_tint_item_pedidos','nekt_raw.mssql_gaspar_dbo_fatura_capa','nekt_raw.mssql_gaspar_dbo_fatura_itens','nekt_raw.mssql_gaspar_dbo_clientes'];
const FIN = ['nekt_service.faturas_unificadas_completo','nekt_raw.mssql_gaspar_dbo_cr_documentos','nekt_raw.mssql_gaspar_dbo_cp_documentos','nekt_raw.mssql_gaspar_dbo_cr_lancamentos','nekt_raw.mssql_gaspar_dbo_cp_lancamentos','nekt_raw.mssql_gaspar_dbo_credito_cliente','nekt_raw.mssql_gaspar_dbo_despesas','nekt_raw.mssql_gaspar_dbo_despesas_subgrupos','nekt_raw.mssql_gaspar_dbo_cp_documentos_despesas','nekt_raw.mssql_gaspar_dbo_cp_documentos_centro_custo_conta_contabil','nekt_raw.mssql_gaspar_dbo_cp_documentos_tributos','nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr','nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr_lancto_cp','nekt_raw.mssql_gaspar_dbo_baixa_cp_contra_cr_lancto_cr','nekt_raw.mssql_gaspar_dbo_nota_fiscal_capa','nekt_raw.mssql_gaspar_dbo_nota_fiscal_eletronica_eventos','nekt_raw.mssql_gaspar_dbo_entradas_itens_lancamentos_saldos','nekt_raw.mssql_gaspar_dbo_cad_tear','nekt_raw.mssql_gaspar_dbo_clientes','nekt_raw.mssql_gaspar_dbo_fornecedores'];
let allowed = null;
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
  const refs = []; const re=/\b(?:from|join)\s+([a-zA-Z_][\w]*\.[a-zA-Z_][\w]*)/gi; let m;
  while((m=re.exec(s))){ refs.push(m[1].toLowerCase()); }
  for(const t of refs){ const sc=t.split('.')[0]; if(['nekt_raw','nekt_service','nekt_trusted'].indexOf(sc) < 0) return { ok:false, motivo:'schema' }; }
  if(allowed !== null){ for(const t of refs){ if(allowed.indexOf(t) < 0) return { ok:false, motivo:'tabela_fora_perfil' }; } }
  if(!permiteRS && MONEY.test(s)) return { ok:false, motivo:'r$' };
  if(!/\blimit\s+\d+/i.test(s)) s = s + ' LIMIT 200';
  if(s.length > 6000) return { ok:false, motivo:'muito_longa' };
  return { ok:true, sql:s };
}
const v = (String(inp.acao)==='sql') ? validar(inp.sql) : { ok:false, motivo:'nao_sql' };
if(v.ok){ const nektObj={ sql:v.sql, mode:'csv', mode_options:{ header:true, delimiter:',' } }; return [{ json:{ nektBody:JSON.stringify(nektObj), sql_reparado:v.sql, ok:true } }]; }
return [{ json:{ nektBody:'', state:'FAILED', ok:false, motivo:(v.motivo||'invalido') } }];
