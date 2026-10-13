// ===== FT · Gerar Ficha — nó "Build HTML" (TEMPLATE FIEL) =====
// Cole TODO este conteúdo no campo jsCode do nó "Build HTML".
// Lê: Parse Nekt, Get Ficha, Agg Prod Cores, Agg Catalogo.
// Assets servidos pelo workflow "FT · Asset Store" (webhook /ft-asset).

const BASE = 'https://soultextil.app.n8n.cloud/webhook/ft-asset?name=';

const p    = $('Parse Nekt').item.json;
const fich = ($('Get Ficha').item.json) || {};
const prod = ($('Agg Prod Cores').item.json.data) || [];
const cat  = ($('Agg Catalogo').item.json.data) || [];

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function cleanNome(d){return String(d||'').replace(/#/g,'').replace(/\s+/g,' ').trim().toUpperCase();}

// ---- campos (Nekt + ft_fichas) ----
const cod   = p.codproduto || '';
const nome  = fich.nome_exibicao ? fich.nome_exibicao : cleanNome(p.descricao);
const comp  = String(p.composicao||'').toUpperCase();
const larg  = p.largramada ? (Number(p.largramada)/100).toFixed(2).replace('.',',')+'m' : '';
const gram  = p.gramramada ? p.gramramada+'g/m²' : '';
const rend  = p.rendimento || '';
const pmed  = p.pesopadrao ? Math.round(Number(p.pesopadrao))+'KG' : '';
const barca = fich.barca_override ? String(fich.barca_override) : ((p.pesopadrao && p.qtdemultipla) ? Math.round(Number(p.pesopadrao)*Number(p.qtdemultipla))+'KG' : '');
// SOBRE A MALHA = cadastro (sobre_texto) com fallback para observacoesgerais do ERP
const sobre = fich.sobre_texto || p.observacoesgerais || '';
const carac = p.caracteristica_texto || fich.caracteristica_texto || '';
const heroUrl = BASE + encodeURIComponent(fich.hero_asset || ('hero_' + cod + '.jpg'));

// SUGESTÕES DE USO = cadastro (sugestoes_json) com fallback para descricaoalternativa separada por "-"
var sugest = [];
try { sugest = fich.sugestoes_json ? JSON.parse(fich.sugestoes_json) : []; } catch(e){ sugest = []; }
if (!sugest.length) { sugest = String(p.descricaoalternativa||'').split('-').map(function(s){return s.trim();}).filter(function(s){return s.length;}); }

// BENEFÍCIOS (4 bullets sob SOBRE A MALHA) = cadastro (beneficios_json); não existe no ERP
var benef = [];
try { benef = fich.beneficios_json ? JSON.parse(fich.beneficios_json) : []; } catch(e){ benef = []; }

// ---- cartela (cores) ----
const m={}; cat.forEach(function(c){ m[String(c.codgrade)] = c; });
// cartela: prioriza cores_json da ft_fichas (cadastro); fallback para ft_produto_cores
var coresIds=[]; try{ coresIds = fich.cores_json ? JSON.parse(fich.cores_json) : []; }catch(e){ coresIds=[]; }
var cores;
if (coresIds.length){
  cores = coresIds.map(function(cg){ var c=m[String(cg)]||{}; return {cod:cg, nome:c.nome||'', hex:c.hex||'#FFFFFF', borda:!!c.tem_borda}; });
} else {
  prod.sort(function(a,b){ return Number(a.ordem)-Number(b.ordem); });
  cores = prod.map(function(pc){ var c=m[String(pc.codgrade)]||{}; return {cod:pc.codgrade, nome:c.nome||'', hex:c.hex||'#FFFFFF', borda:!!c.tem_borda}; });
}

// ---- ícones padrão Soul (fixos v1; por produto depois via ft_produto_icones) ----
const icones = [
  {id:'easycare',     label:'Easy Care'},
  {id:'elasticidade', label:'Elasticidade'},
  {id:'shape',        label:'Shape'},
  {id:'toquemacio',   label:'Toque Macio'},
  {id:'conforto',     label:'Conforto'}
];

// ---- cartela: posições exatas do mapa (14 amostras) ----
const SW_X = [36.30,73.96,111.73,149.39,187.06,224.73,262.39,300.06,338.58,374.84,412.04,449.25,486.46,523.67];
const LG_X = [54.52,91.64,128.75,165.86,202.96,240.07,277.18,314.30,353.49,391.37,428.45,465.55,502.63,539.73];
let swHtml='';
for (let i=0;i<cores.length && i<14;i++){
  const c=cores[i]; const x=SW_X[i]!=null?SW_X[i]:(36.30+i*37.5); const lx=LG_X[i]!=null?LG_X[i]:x+14;
  const top = (i===8)?638.59:638.33;
  const style = c.borda ? 'background:#fff;border:1.5pt solid #000;' : ('background:'+c.hex+';');
  swHtml += '<div class="sw" style="left:'+x+'pt;top:'+top+'pt;'+style+'"></div>';
  const nm = esc(c.nome).replace(/ /g,'<br>'); // nomes de 2 palavras quebram
  swHtml += '<div class="abs ctr" style="left:'+lx+'pt;top:672.2pt;width:40pt"><div class="t-colcode">'+esc(c.cod)+'</div><div class="t-colname">'+nm+'</div></div>';
}

// ---- sugestões (lista no painel) ----
let sugHtml='';
for (let i=0;i<sugest.length;i++){ sugHtml += '<div><span class="bul"></span>'+esc(sugest[i])+'</div>'; }

// ---- benefícios (4 bullets sob SOBRE A MALHA; baselines mapa: 552,38 / 566,64 / 580,90 / 595,15) ----
let benHtml='';
if (benef.length){
  benHtml = '<div class="abs t-body list" style="left:42.25pt;top:545.84pt;width:320pt">';
  for (let i=0;i<benef.length;i++){ benHtml += '<div><span class="bul"></span>'+esc(benef[i])+'</div>'; }
  benHtml += '</div>';
}

// ---- ícones (faixa Z7) ----
const IC_X=[164.53,217.89,270.51,319.25,372.58], IC_Y=[717.43,720.05,719.37,721.10,717.98], IC_W=[56.27,55.52,56.27,55.52,62.27], IC_H=[57.02,55.52,56.27,55.52,62.27];
const LEG_CX=[192.79,245.74,298.65,349.01,403.54], LEG_TOP=[763.73,762.98,765.82,766.82,766.83];
const DIV_X=[218.86,276.58,319.73,377.35];
let icHtml='';
for (let i=0;i<icones.length && i<5;i++){
  icHtml += '<img class="abs" src="'+BASE+'icon_'+icones[i].id+'.png" style="left:'+IC_X[i]+'pt;top:'+IC_Y[i]+'pt;width:'+IC_W[i]+'pt;height:'+IC_H[i]+'pt">';
  icHtml += '<div class="abs t-iconleg ctr" style="left:'+LEG_CX[i]+'pt;top:'+LEG_TOP[i]+'pt;width:72pt">'+esc(icones[i].label)+'</div>';
}
let icDiv='';
for (let i=0;i<DIV_X.length;i++){ icDiv += '<div class="vdiv" style="left:'+DIV_X[i]+'pt;top:733.16pt;height:35.36pt"></div>'; }

const html =
'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
+'<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400&display=swap" rel="stylesheet">'
+'<style>'
+"@font-face{font-family:'GS';src:url('"+BASE+"GillSansMT-Regular.ttf') format('truetype')}"
+"@font-face{font-family:'GSB';src:url('"+BASE+"GillSans-Bold.ttf') format('truetype')}"
+"@font-face{font-family:'GSL';src:url('"+BASE+"GillSans-Light.ttf') format('truetype')}"
+"@font-face{font-family:'Anton';src:url('"+BASE+"Anton.ttf') format('truetype')}"
+'@page{size:595.5pt 842.25pt;margin:0}*{margin:0;padding:0;box-sizing:border-box}'
+'html,body{width:595.5pt;height:842.25pt}.page{position:relative;width:595.5pt;height:842.25pt;background:#fff;overflow:hidden;color:#000}'
+'.abs{position:absolute}.ctr{text-align:center;transform:translateX(-50%)}'
+'.t-art{font-family:GSL;font-size:13.06pt;line-height:1;white-space:nowrap}'
+'.t-title{font-family:Anton;font-weight:400;font-size:58.8pt;line-height:1;white-space:nowrap;transform:scaleX(0.64);transform-origin:left top}'
+'.t-label{font-family:GSB;font-size:9.59pt;line-height:1;white-space:nowrap}'
+'.t-panel{font-family:GSB;font-size:14pt;line-height:1;white-space:nowrap}'
+'.t-body{font-family:GS;font-size:9.59pt;line-height:14.26pt}'
+'.t-val{font-family:GS;font-size:9.59pt;line-height:1;white-space:nowrap}'
+'.t-colcode,.t-colname{font-family:"Open Sans";font-size:7.59pt;line-height:7.9pt;text-align:center}'
+'.t-iconleg{font-family:GS;font-size:8.61pt;line-height:1;text-align:center;white-space:nowrap}'
+'.t-foot{font-family:GS;font-size:8pt;line-height:9pt}'
+'.hero-clip{left:0;top:0;width:595.5pt;height:280.61pt;overflow:hidden}.hero-clip img{position:absolute;left:-34.15pt;top:-307.15pt;width:673pt;height:898.09pt}'
+'.panel{left:382.36pt;top:309.25pt;width:178.65pt;height:270.76pt;background:#ECECEC}'
+'.vdiv{position:absolute;width:.75pt;background:#000}'
+'.list div{position:relative;padding-left:8.8pt}.bul{position:absolute;left:0;top:50%;width:2.25pt;height:2.25pt;border-radius:50%;background:#000;transform:translateY(-50%)}'
+'.sw{position:absolute;width:29.57pt;height:31.19pt;border-radius:7.5pt}'
+'.foot-band{left:0;top:800.83pt;width:595.48pt;height:41.38pt;background:#CFB58A}'
+'.folha-clip{left:95.35pt;top:812.28pt;width:20.26pt;height:19.51pt;overflow:hidden}.folha-clip img{position:absolute;left:-12.59pt;top:-13.75pt;width:45.77pt;height:45.77pt}'
+'</style></head><body><div class="page">'
+'<div class="abs hero-clip"><img src="'+heroUrl+'"></div>'
+'<div class="abs t-art" style="left:36.21pt;top:301.1pt">ARTIGO: '+esc(cod)+'</div>'
+'<div class="abs t-title" style="left:34.75pt;top:313pt">'+esc(nome)+'</div>'
+'<div class="abs panel"></div>'
+'<img class="abs" src="'+BASE+'logo.png" style="left:415.05pt;top:320.53pt;width:113.29pt;height:27.01pt">'
+'<div class="abs t-panel ctr" style="left:471.68pt;top:367.43pt">COLEÇÃO</div>'
+'<div class="abs t-label" style="left:402.09pt;top:415.37pt">SUGESTÕES DE USO:</div>'
+'<div class="abs t-body list" style="left:409.59pt;top:427.7pt">'+sugHtml+'</div>'
+'<div class="abs t-label ctr" style="left:69.77pt;top:405.99pt">COMPOSIÇÃO</div><div class="abs t-val ctr" style="left:68.14pt;top:421.39pt">'+esc(comp)+'</div>'
+'<div class="vdiv" style="left:112.25pt;top:408.52pt;height:19.09pt"></div>'
+'<div class="abs t-label ctr" style="left:144.09pt;top:405.99pt">LARGURA</div><div class="abs t-val ctr" style="left:143.30pt;top:421.39pt">'+esc(larg)+'</div>'
+'<div class="vdiv" style="left:177.56pt;top:409.05pt;height:19.09pt"></div>'
+'<div class="abs t-label ctr" style="left:218.45pt;top:405.99pt">GRAMATURA</div><div class="abs t-val ctr" style="left:218.46pt;top:421.39pt">'+esc(gram)+'</div>'
+'<div class="vdiv" style="left:263.72pt;top:409.93pt;height:19.09pt"></div>'
+'<div class="abs t-label ctr" style="left:309.39pt;top:405.99pt">RENDIMENTO</div><div class="abs t-val ctr" style="left:306.39pt;top:421.39pt">'+esc(rend)+'</div>'
+'<div class="abs t-label" style="left:36.20pt;top:464.99pt">SOBRE A MALHA:</div>'
+'<div class="abs t-body" style="left:36.20pt;top:479.24pt;width:345pt">'+esc(sobre).replace(/\n/g,'<br>')+'</div>'
+benHtml
+'<div class="abs t-label" style="left:33.46pt;top:623.28pt">CARTELA DE CORES:</div>'
+swHtml
+'<div class="abs t-val ctr" style="left:297.18pt;top:704.9pt">PESO MÉDIO DA PEÇA '+esc(pmed)+' - PESO DA BARCA DE TINGIMENTO '+esc(barca)+'</div>'
+icHtml+icDiv
+'<div class="abs foot-band"></div>'
+'<div class="abs folha-clip"><img src="'+BASE+'folha.png"></div>'
+'<div class="abs t-foot" style="left:117.80pt;top:815pt">Produto desenvolvido com<br>tecnologia e responsabilidade</div>'
+'<div class="vdiv" style="left:221.44pt;top:815.03pt;height:19.09pt"></div>'
+'<div class="abs t-foot" style="left:238pt;top:820.5pt">&#64;soultextil</div>'
+'<div class="vdiv" style="left:298.33pt;top:815.03pt;height:19.09pt"></div>'
+'<div class="abs t-foot" style="left:315pt;top:820.5pt">www.soultextil.com.br</div>'
+'<div class="vdiv" style="left:409.97pt;top:813.90pt;height:19.09pt"></div>'
+'<div class="abs t-foot" style="left:426pt;top:820.5pt">0800 278 0018</div>'
+'</div></body></html>';

return [{ json: { html: html } }];
