
const raw = String(($input.first() && ($input.first().json.data || $input.first().json.body)) || '');
const ctx = $('Prep').first().json.ctx;
const pr = $('Rotear').first().json;
function parseLine(line){ const out=[]; let cur=''; let q=false; for(let i=0;i<line.length;i++){ const ch=line[i]; if(q){ if(ch==='"'){ if(line[i+1]==='"'){cur+='"';i++;} else {q=false;} } else cur+=ch; } else { if(ch==='"') q=true; else if(ch===',') { out.push(cur); cur=''; } else cur+=ch; } } out.push(cur); return out; }
const permiteRS = !!ctx.permite_rs;
const PII = /(cnpj|cpf|identidade|\brg\b|telefone|celular|\bfax\b|email|e_mail|senha|password)/i;
const MONEY = /(valor|vlr|preco|custo|saldo|_rs$|reais|faturamento)/i;
function colBloqueada(nome){ const n=String(nome||''); if(PII.test(n)) return true; if(!permiteRS && MONEY.test(n)) return true; return false; }
const lines = raw.split(/\r?\n/).filter(function(x){ return x.length>0; });
let dados_texto='(sem resultados)'; let n=0;
if(lines.length>=1){
  let header=parseLine(lines[0]);
  const keep=[]; for(let i=0;i<header.length;i++){ if(!colBloqueada(header[i])) keep.push(i); }
  header = keep.map(function(i){ return header[i]; });
  const rows=[]; for(let i=1;i<lines.length && i<=60;i++){ const full=parseLine(lines[i]); rows.push(keep.map(function(k){ return full[k]; })); }
  n = Math.max(0, lines.length-1);
  if(rows.length===0){ dados_texto='(nenhum registro encontrado para os filtros informados)'; }
  else if(header.length===0){ dados_texto='(sem colunas disponiveis para o seu perfil)'; }
  else { let t=header.join(' | ')+String.fromCharCode(10)+header.map(function(){return '---';}).join(' | '); for(const rr of rows){ t+=String.fromCharCode(10)+rr.join(' | '); } dados_texto=t; }
}
const isRS = permiteRS;
const regra = isRS ? 'Valores em R$ sao permitidos para este perfil.' : 'Responda SEMPRE em kg, pecas e percentuais. NUNCA mostre valores em R$.';
const sys = 'Voce e o assistente de IA da Soul Textil para o perfil '+(ctx.area||ctx.perfil_efetivo)+'. Responda de forma objetiva e profissional SOMENTE com base nos DADOS abaixo; nao invente numeros nem colunas. '+regra+' Filiais na coluna origem: GASPAR=Gaspar (SC), LOJASP=Filial SP, MATRIZ=Filial PE. Use tabelas markdown quando houver varias linhas/colunas. Se os dados vierem vazios, diga que nao ha registros para o filtro e sugira ajustar o periodo ou o termo.';
const userMsg = ctx.mensagem + String.fromCharCode(10) + String.fromCharCode(10) + '--- DADOS (fonte: '+(pr.fonte||'ERP Soul')+') ---' + String.fromCharCode(10) + dados_texto;
const answerObj = { model: ctx.modelo, max_tokens:1200, system: sys, messages:[{ role:'user', content: userMsg }] };
return [{ json:{ answerBody: JSON.stringify(answerObj), dados_n:n } }];
