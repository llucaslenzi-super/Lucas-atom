
const ctx = $('Prep').first().json.ctx;
const planner = JSON.parse($('Prep').first().json.routerBody);
const pr = $('Rotear').first().json;
const fail = ($input.first() && $input.first().json) || {};
const reason = String(fail.state_change_reason || fail.error || fail.message || 'erro desconhecido').slice(0,600);
const badSql = pr.sql_gerado || '';
const reparo = { model:'claude-sonnet-5', max_tokens:1500, system: planner.system, tools: planner.tools, tool_choice: planner.tool_choice, messages:[{ role:'user', content: ctx.mensagem + String.fromCharCode(10)+String.fromCharCode(10)+'[Sistema: a consulta SQL anterior FALHOU no Athena. SQL: '+badSql+' | Erro: '+reason+'. Gere uma NOVA consulta SQL corrigida (acao=sql) usando SOMENTE colunas e tabelas que existam no catalogo. Se realmente nao for possivel, use acao=fora_escopo.]' }] };
return [{ json:{ reparoBody: JSON.stringify(reparo), reason:reason } }];
