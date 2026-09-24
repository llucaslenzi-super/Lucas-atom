// Plataforma Soul · Auth — workflow n8n (SDK)
// Webhooks: POST /plat/api/login, POST /plat/api/logout, GET /plat/api/me
// Login: pbkdf2 100k SHA-256 (base64) contra plat_usuarios; token HMAC-SHA256 base64url 8h.
// Independente dos workflows existentes. Workflow ID em produção: dRRnEVOFNfEbyEI6
// Tabelas: plat_config M9nV4qaH2NsFOA0X · plat_usuarios Ow8JHh7IQiaGhSkl
import { workflow, node, trigger, ifElse, expr } from '@n8n/workflow-sdk';

const VERIFY_JS = `
const crypto = require('crypto');
const body = ($('Webhook Login').first().json.body) || {};
const usuario = String(body.usuario || '').trim().toLowerCase();
const senha = String(body.senha || '');
const sr = $('Get HMAC Login').first();
const secret = (sr && sr.json.valor) || '';
const u = ($input.first() && $input.first().json) || {};
if (!secret) return [{json:{statusCode:500, body:{sucesso:false, erro:'sem_config'}}}];
if (!usuario || !senha) return [{json:{statusCode:400, body:{sucesso:false, erro:'campos_obrigatorios'}}}];
if (!u.usuario) return [{json:{statusCode:401, body:{sucesso:false, erro:'credenciais_invalidas'}}}];
if (u.ativo === false) return [{json:{statusCode:403, body:{sucesso:false, erro:'usuario_suspenso'}}}];
const salt = Buffer.from(String(u.salt||''), 'base64');
const calc = crypto.pbkdf2Sync(senha, salt, 100000, 64, 'sha256');
const stored = Buffer.from(String(u.hash_senha||''), 'base64');
let ok = false;
try { ok = calc.length === stored.length && crypto.timingSafeEqual(calc, stored); } catch(e) { ok = false; }
if (!ok) return [{json:{statusCode:401, body:{sucesso:false, erro:'credenciais_invalidas'}}}];
const exp = new Date(Date.now() + 8*3600*1000).toISOString();
const payload = { usuario:u.usuario, nome:u.nome, perfil:u.perfil, nivel:u.nivel, area:u.area, is_admin:!!u.is_admin, exp };
const p64 = Buffer.from(JSON.stringify(payload)).toString('base64url');
const sig = crypto.createHmac('sha256', secret).update(p64).digest('base64url');
const token = p64 + '.' + sig;
return [{json:{statusCode:200, body:{ sucesso:true, token, usuario:u.usuario, nome:u.nome, perfil:u.perfil, nivel:u.nivel, area:u.area, is_admin:!!u.is_admin, expira_em:exp }}}];
`;

const VALIDATE_ME_JS = `
const crypto = require('crypto');
const req = $('Webhook Me').first().json;
const headers = req.headers || {};
const q = req.query || {};
const auth = String(headers.authorization || headers.Authorization || '');
const token = (auth.toLowerCase().indexOf('bearer ') === 0 ? auth.slice(7).trim() : auth.trim()) || String(q.token || '');
const sr = $('Get HMAC Me').first();
const secret = (sr && sr.json.valor) || '';
if (!secret) return [{json:{valido:false, statusCode:500, body:{sucesso:false, erro:'sem_config'}}}];
if (!token) return [{json:{valido:false, statusCode:401, body:{sucesso:false, erro:'sem_token'}}}];
const parts = token.split('.');
if (parts.length !== 2) return [{json:{valido:false, statusCode:401, body:{sucesso:false, erro:'token_invalido'}}}];
function toBuf(s){ const t = s.replace(/-/g,'+').replace(/_/g,'/'); const pad = (4 - (t.length % 4)) % 4; return Buffer.from(t + '='.repeat(pad), 'base64'); }
const expected = crypto.createHmac('sha256', secret).update(parts[0]).digest();
let provided;
try { provided = toBuf(parts[1]); } catch(e){ return [{json:{valido:false, statusCode:401, body:{sucesso:false, erro:'assinatura_invalida'}}}]; }
if (expected.length !== provided.length || !crypto.timingSafeEqual(expected, provided)) return [{json:{valido:false, statusCode:401, body:{sucesso:false, erro:'assinatura_invalida'}}}];
let payload;
try { payload = JSON.parse(toBuf(parts[0]).toString('utf8')); } catch(e){ return [{json:{valido:false, statusCode:401, body:{sucesso:false, erro:'payload_invalido'}}}]; }
if (!payload.exp || new Date(payload.exp).getTime() < Date.now()) return [{json:{valido:false, statusCode:401, body:{sucesso:false, erro:'expirado'}}}];
return [{json:{valido:true, statusCode:200, payload}}];
`;

const BUILD_ME_JS = `
const p = $('Validate Me').first().json.payload;
const u = ($input.first() && $input.first().json) || {};
let fontes = [];
try { fontes = JSON.parse(u.fontes || '[]'); } catch(e) { fontes = []; }
return [{json:{ statusCode:200, body:{ sucesso:true, usuario:p.usuario, nome:p.nome, perfil:p.perfil, nivel:p.nivel, area:p.area, is_admin:!!p.is_admin, cargo:u.cargo||'', fontes, expira_em:p.exp } }}];
`;

const whLogin = trigger({ type:'n8n-nodes-base.webhook', version:2.1, config:{ name:'Webhook Login', parameters:{ httpMethod:'POST', path:'plat/api/login', responseMode:'responseNode', options:{} } }, output:[{ body:{ usuario:'diretoria@soultextil.com.br', senha:'x' } }] });
const getSecretLogin = node({ type:'n8n-nodes-base.dataTable', version:1.1, config:{ name:'Get HMAC Login', parameters:{ resource:'row', operation:'get', dataTableId:{ __rl:true, mode:'id', value:'M9nV4qaH2NsFOA0X', cachedResultName:'plat_config' }, matchType:'allConditions', filters:{ conditions:[{ keyName:'chave', condition:'eq', keyValue:'hmac_secret' }] }, returnAll:false, limit:1 } }, output:[{ chave:'hmac_secret', valor:'secret' }] });
const getUserLogin = node({ type:'n8n-nodes-base.dataTable', version:1.1, config:{ name:'Get User Login', parameters:{ resource:'row', operation:'get', dataTableId:{ __rl:true, mode:'id', value:'Ow8JHh7IQiaGhSkl', cachedResultName:'plat_usuarios' }, matchType:'allConditions', filters:{ conditions:[{ keyName:'usuario', condition:'eq', keyValue: expr('{{ $(\"Webhook Login\").item.json.body.usuario }}') }] }, returnAll:false, limit:1 }, alwaysOutputData:true }, output:[{ usuario:'diretoria@soultextil.com.br', ativo:true }] });
const verifyLogin = node({ type:'n8n-nodes-base.code', version:2, config:{ name:'Verify Login', parameters:{ mode:'runOnceForAllItems', language:'javaScript', jsCode: VERIFY_JS }, executeOnce:true }, output:[{ statusCode:200, body:{ sucesso:true } }] });
const respLogin = node({ type:'n8n-nodes-base.respondToWebhook', version:1.5, config:{ name:'Respond Login', parameters:{ respondWith:'json', responseBody: expr('{{ $json.body }}'), options:{ responseCode: expr('{{ $json.statusCode }}') } } }, output:[{}] });

const whLogout = trigger({ type:'n8n-nodes-base.webhook', version:2.1, config:{ name:'Webhook Logout', parameters:{ httpMethod:'POST', path:'plat/api/logout', responseMode:'responseNode', options:{} } }, output:[{}] });
const respLogout = node({ type:'n8n-nodes-base.respondToWebhook', version:1.5, config:{ name:'Respond Logout', parameters:{ respondWith:'json', responseBody: expr('{{ { \"sucesso\": true, \"mensagem\": \"sessao encerrada\" } }}'), options:{} } }, output:[{}] });

const whMe = trigger({ type:'n8n-nodes-base.webhook', version:2.1, config:{ name:'Webhook Me', parameters:{ httpMethod:'GET', path:'plat/api/me', responseMode:'responseNode', options:{} } }, output:[{ headers:{ authorization:'Bearer x' } }] });
const getSecretMe = node({ type:'n8n-nodes-base.dataTable', version:1.1, config:{ name:'Get HMAC Me', parameters:{ resource:'row', operation:'get', dataTableId:{ __rl:true, mode:'id', value:'M9nV4qaH2NsFOA0X', cachedResultName:'plat_config' }, matchType:'allConditions', filters:{ conditions:[{ keyName:'chave', condition:'eq', keyValue:'hmac_secret' }] }, returnAll:false, limit:1 } }, output:[{ valor:'secret' }] });
const validateMe = node({ type:'n8n-nodes-base.code', version:2, config:{ name:'Validate Me', parameters:{ mode:'runOnceForAllItems', language:'javaScript', jsCode: VALIDATE_ME_JS }, executeOnce:true }, output:[{ valido:true, payload:{ usuario:'diretoria@soultextil.com.br' } }] });
const ifMe = ifElse({ version:2.2, config:{ name:'Token Valido?', parameters:{ conditions:{ options:{ caseSensitive:true, leftValue:'', typeValidation:'loose' }, conditions:[{ leftValue: expr('{{ $json.valido }}'), operator:{ type:'boolean', operation:'true' }, rightValue:'' }], combinator:'and' } } } });
const getUserMe = node({ type:'n8n-nodes-base.dataTable', version:1.1, config:{ name:'Get User Me', parameters:{ resource:'row', operation:'get', dataTableId:{ __rl:true, mode:'id', value:'Ow8JHh7IQiaGhSkl', cachedResultName:'plat_usuarios' }, matchType:'allConditions', filters:{ conditions:[{ keyName:'usuario', condition:'eq', keyValue: expr('{{ $(\"Validate Me\").item.json.payload.usuario }}') }] }, returnAll:false, limit:1 }, alwaysOutputData:true }, output:[{ usuario:'diretoria@soultextil.com.br', fontes:'[]' }] });
const buildMe = node({ type:'n8n-nodes-base.code', version:2, config:{ name:'Build Me', parameters:{ mode:'runOnceForAllItems', language:'javaScript', jsCode: BUILD_ME_JS }, executeOnce:true }, output:[{ statusCode:200, body:{ sucesso:true } }] });
const respMeOk = node({ type:'n8n-nodes-base.respondToWebhook', version:1.5, config:{ name:'Respond Me OK', parameters:{ respondWith:'json', responseBody: expr('{{ $json.body }}'), options:{ responseCode: expr('{{ $json.statusCode }}') } } }, output:[{}] });
const respMeErr = node({ type:'n8n-nodes-base.respondToWebhook', version:1.5, config:{ name:'Respond Me Erro', parameters:{ respondWith:'json', responseBody: expr('{{ $json.body }}'), options:{ responseCode: expr('{{ $json.statusCode }}') } } }, output:[{}] });

export default workflow('plataforma-soul-auth', 'Plataforma Soul · Auth')
  .add(whLogin).to(getSecretLogin).to(getUserLogin).to(verifyLogin).to(respLogin)
  .add(whLogout).to(respLogout)
  .add(whMe).to(getSecretMe).to(validateMe).to(ifMe.onTrue(getUserMe.to(buildMe).to(respMeOk)).onFalse(respMeErr));
