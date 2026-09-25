
const crypto = require('crypto');
const ctx = $('Prep').first().json.ctx;
const pr = $('Rotear').first().json;
const texto = 'Consultei o ERP, mas nao consegui obter os dados para essa pergunta agora. Pode reformular ou detalhar melhor (produto, periodo, filial)? Perguntas mais especificas costumam funcionar melhor.';
const preco = { 'claude-sonnet-5':{i:3,o:15} }; const fx=5.4; const pR=preco['claude-sonnet-5'];
const custo=Math.round((((pr.router_in||0)*pR.i+(pr.router_out||0)*pR.o)/1000000*fx)*10000)/10000;
const uid='i-'+crypto.randomUUID(); const criado=new Date().toISOString();
return [{ json:{ uid:uid, criado_em:criado, usuario:ctx.usuario, area:ctx.area, perfil:ctx.perfil, modelo:ctx.modelo, tokens_in:(pr.router_in||0), tokens_out:(pr.router_out||0), custo:custo, prompt:ctx.mensagem_raw, resposta:texto, guardrails:JSON.stringify(ctx.guardrails), alerta:(ctx.alerta||'sem_dados'), fonte:(pr.fonte||'ERP Soul'), conversa_id:ctx.conversa_id, ip:ctx.ip, dispositivo:ctx.dispositivo, feedback:'', body:{ sucesso:true, resposta:texto, fonte:(pr.fonte||''), modelo:ctx.modelo, conversa_id:ctx.conversa_id, interacao_id:uid, custo:custo, alerta:(ctx.alerta||'sem_dados'), guardrails:ctx.guardrails, dados_n:0 } } }];
