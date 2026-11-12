# -*- coding: utf-8 -*-
"""
Os workflows do Agente de Prospecção, como código.

Rode daqui para recriar ou corrigir tudo na Atom:

    export N8N_JWT=...  APP_SENHA=...  PONTE_TOKEN=...
    python3 publicar.py              # os cinco
    python3 publicar.py api app      # só esses

Isto existe porque workflow clicado na tela não tem histórico, não tem
revisão e não volta se alguém apagar. Aqui ele é texto, com motivo escrito
ao lado de cada decisão, e `publicar` é idempotente: atualiza o que já
existe pelo nome e cria o que falta.

REGRA DE INSTÂNCIA: só a Atom. As ferramentas MCP de n8n desta sessão
apontam para a soultextil, então nada aqui passa por elas — tudo é a API
REST com o JWT, e `atom.py` recusa qualquer outro host.
"""
import json
import os
import sys

from atom import api, tabela, workflow, PROJETO

# Segredos NUNCA entram no arquivo: o repositório é público.
#     export APP_SENHA=...      a senha da tela
#     export PONTE_TOKEN=...    o mesmo de /etc/misner.env na VM
SENHA = os.environ.get("APP_SENHA", "").strip()
TOKEN = os.environ.get("PONTE_TOKEN", "").strip()
if not SENHA or not TOKEN:
    raise SystemExit("faltam APP_SENHA e PONTE_TOKEN no ambiente")

def rl(nome):
    t = tabela(nome)
    if not t: raise SystemExit("falta a Data Table " + nome)
    return {"__rl": True, "mode": "id", "value": t["id"], "cachedResultName": nome}

UI        = rl("prospeccao_ui")
PEDIDOS   = rl("prospeccao_pedidos")
LISTAS    = rl("prospeccao_listas")
ARQUIVOS  = rl("prospeccao_arquivos")
ENTREGUES = rl("prospeccao_entregues")

def no(nome, tipo, v, pos, params, **extra):
    d = {"name": nome, "type": "n8n-nodes-base." + tipo, "typeVersion": v,
         "position": pos, "parameters": params}
    d.update(extra); return d

def webhook(nome, metodo, caminho, pos):
    return no(nome, "webhook", 2.2, pos, {"httpMethod": metodo, "path": caminho,
              "responseMode": "responseNode", "options": {}})

def se(nome, expr, pos):
    return no(nome, "if", 2.2, pos, {"conditions": {
        "options": {"caseSensitive": True, "leftValue": "",
                    "typeValidation": "loose", "version": 2},
        "conditions": [{"id": "c1", "leftValue": expr, "rightValue": True,
                        "operator": {"type": "boolean", "operation": "true",
                                     "singleValue": True}}],
        "combinator": "and"}, "looseTypeValidation": True, "options": {}})

def codigo(nome, js, pos):
    return no(nome, "code", 2, pos, {"language": "javaScript",
              "mode": "runOnceForAllItems", "jsCode": js})

def le(nome, tab, condicoes, pos, uma_vez=False):
    d = no(nome, "dataTable", 1.1, pos, {
        "resource": "row", "operation": "get", "dataTableId": tab,
        "matchType": "allConditions",
        "filters": {"conditions": condicoes},
        "returnAll": True}, alwaysOutputData=True)
    if uma_vez: d["executeOnce"] = True
    return d

def grava(nome, tab, chave_col, chave_val, colunas, pos):
    return no(nome, "dataTable", 1.1, pos, {
        "resource": "row", "operation": "upsert", "dataTableId": tab,
        "matchType": "allConditions",
        "filters": {"conditions": [{"keyName": chave_col, "condition": "eq",
                                    "keyValue": chave_val}]},
        "columns": {"mappingMode": "defineBelow", "value": colunas}})

def responde(nome, corpo, pos, codigo_http=None, texto=False, cabecalhos=None):
    o = {}
    if codigo_http: o["responseCode"] = codigo_http
    if cabecalhos:
        o["responseHeaders"] = {"entries": [{"name": k, "value": v}
                                            for k, v in cabecalhos.items()]}
    return no(nome, "respondToWebhook", 1.1, pos, {
        "respondWith": "text" if texto else "json",
        "responseBody": corpo, "options": o})

def liga(*pares):
    c = {}
    for a, b in pares:
        c.setdefault(a, {"main": [[]]})
        c[a]["main"][0].append({"node": b, "type": "main", "index": 0})
    return c

def liga_se(c, nome, verdadeiro, falso):
    c[nome] = {"main": [[{"node": verdadeiro, "type": "main", "index": 0}],
                        [{"node": falso, "type": "main", "index": 0}]]}
    return c

# ─────────────────────────────────────────────── Guardar
JS_VALIDA = """// Quem chama aqui é a ponte, de dentro da VM.
const SEGREDO = %s;
const b = $json.body || {};
if (b.token !== SEGREDO) return [{ json: { ok: false, erro: 'token' } }];
const falta = ['pedido_id','fatia','formato','b64','filename']
  .filter(function (k) { return !b[k] && b[k] !== 0; });
if (falta.length) return [{ json: { ok: false, erro: 'faltam: ' + falta.join(',') } }];
// A chave é pedido-fatia-formato: reenvio da MESMA fatia sobrescreve em vez
// de duplicar, então a ponte pode morrer no meio sem estragar nada.
const chave = b.pedido_id + '-' + String(b.fatia).padStart(3, '0') + '-' + b.formato;
return [{ json: {
  ok: true, chave: chave,
  pedido_id: String(b.pedido_id), fatia: Number(b.fatia),
  formato: String(b.formato), filename: String(b.filename),
  ct: String(b.ct || 'application/octet-stream'),
  b64: String(b.b64),
  empresas: Number(b.empresas || 0),
  novas: Number(b.novas || 0), repetidas: Number(b.repetidas || 0),
  criado_em: new Date().toISOString()
} }];""" % json.dumps(TOKEN)

guardar = {
 "name": "Prospecção · Guardar",
 "settings": {"executionOrder": "v1"},
 "nodes": [
   webhook("Guardar", "POST", "prospeccao-guardar", [0, 0]),
   codigo("Valida", JS_VALIDA, [224, 0]),
   se("Autorizado?", "={{ $json.ok }}", [448, 0]),
   # O arquivo pesado mora sozinho. A tabela que a tela lê fica leve.
   grava("Grava arquivo", ARQUIVOS, "chave", "={{ $json.chave }}", {
     "chave": "={{ $json.chave }}", "ct": "={{ $json.ct }}",
     "filename": "={{ $json.filename }}", "b64": "={{ $json.b64 }}",
     "criado_em": "={{ $json.criado_em }}"}, [672, -96]),
   grava("Grava índice", LISTAS, "chave", "={{ $('Valida').first().json.chave }}", {
     "chave": "={{ $('Valida').first().json.chave }}",
     "pedido_id": "={{ $('Valida').first().json.pedido_id }}",
     "fatia": "={{ $('Valida').first().json.fatia }}",
     "formato": "={{ $('Valida').first().json.formato }}",
     "filename": "={{ $('Valida').first().json.filename }}",
     "empresas": "={{ $('Valida').first().json.empresas }}",
     "novas": "={{ $('Valida').first().json.novas }}",
     "repetidas": "={{ $('Valida').first().json.repetidas }}",
     "criado_em": "={{ $('Valida').first().json.criado_em }}"}, [896, -96]),
   responde("Ok", "={{ { ok: true, chave: $('Valida').first().json.chave } }}", [1120, -96]),
   responde("Recusado", "={{ { ok: false, erro: $json.erro } }}", [672, 96], 401),
 ],
 "connections": liga_se(liga(("Guardar", "Valida"), ("Valida", "Autorizado?"),
                             ("Grava arquivo", "Grava índice"),
                             ("Grava índice", "Ok")),
                        "Autorizado?", "Grava arquivo", "Recusado"),
}

# ─────────────────────────────────────────────── Baixar
JS_BIN = """// base64 da Data Table vira binário, e o Respond devolve como arquivo.
const r = $('Pega arquivo').first().json || {};
const b64 = (r.b64 || '').toString();
if (!b64) {
  // Chave errada, ou lista já apagada pela retenção de 7 dias. Melhor dizer
  // isso do que entregar um arquivo de zero byte, que parece corrupção.
  return [{ json: { erro: 'lista não encontrada ou já expirada' } }];
}
const ct = (r.ct || 'application/octet-stream').toString();
const fn = (r.filename || 'lista').toString();
return [{ json: { ok: true }, binary: { data: { data: b64, mimeType: ct, fileName: fn } } }];"""

baixar = {
 "name": "Prospecção · Baixar",
 "settings": {"executionOrder": "v1"},
 "nodes": [
   webhook("Baixar", "GET", "prospeccao-baixar", [0, 0]),
   le("Pega arquivo", ARQUIVOS,
      [{"keyName": "chave", "condition": "eq",
        "keyValue": "={{ ($json.query && $json.query.c) || '' }}"}], [224, 0]),
   codigo("Bin", JS_BIN, [448, 0]),
   se("Tem arquivo?", "={{ $json.ok }}", [672, 0]),
   no("Entrega", "respondToWebhook", 1.1, [896, -96], {
      "respondWith": "binary", "responseBinaryPropertyName": "data",
      "options": {"responseHeaders": {"entries": [
        {"name": "Content-Disposition",
         "value": "=attachment; filename=\"{{ $('Pega arquivo').first().json.filename }}\""}]}}}),
   responde("Não achou", "={{ { erro: $json.erro || 'não encontrada' } }}", [896, 96], 404),
 ],
 "connections": liga_se(liga(("Baixar", "Pega arquivo"), ("Pega arquivo", "Bin"),
                             ("Bin", "Tem arquivo?")),
                        "Tem arquivo?", "Entrega", "Não achou"),
}

# ─────────────────────────────────────────────── Limpar
def apaga(nome, tab, dias, pos):
    return no(nome, "dataTable", 1.1, pos, {
        "resource": "row", "operation": "deleteRows", "dataTableId": tab,
        "matchType": "allConditions",
        "filters": {"conditions": [{"keyName": "criado_em", "condition": "lt",
                    "keyValue": "={{ $now.minus(%d, 'days').toISO() }}" % dias}]}})

limpar = {
 "name": "Prospecção · Limpar",
 "settings": {"executionOrder": "v1"},
 "nodes": [
   no("Todo dia", "scheduleTrigger", 1.2, [0, 0],
      {"rule": {"interval": [{"triggerAtHour": 4}]}}),
   # 7 dias é o que mantém os 50 MB de Data Table da instância sob controle.
   apaga("Arquivos velhos", ARQUIVOS, 7, [224, 0]),
   apaga("Índices velhos", LISTAS, 7, [448, 0]),
   # O registro de entregues é leve e é memória do negócio: fica 180 dias.
   apaga("Entregues antigos", ENTREGUES, 180, [672, 0]),
   # O histórico de pedidos é o que a tela mostra em "Minhas listas". Sem
   # isto ele cresceria para sempre: o arquivo expira em 7 dias, o cartão
   # ficaria na tela anos depois sem botão nenhum.
   apaga("Pedidos antigos", PEDIDOS, 60, [896, 0]),
 ],
 "connections": liga(("Todo dia", "Arquivos velhos"),
                     ("Arquivos velhos", "Índices velhos"),
                     ("Índices velhos", "Entregues antigos"),
                     ("Entregues antigos", "Pedidos antigos")),
}

# ─────────────────────────────────────────────── App (serve o HTML)
app = {
 "name": "Prospecção · App",
 "settings": {"executionOrder": "v1"},
 "nodes": [
   webhook("Abre", "GET", "prospeccao", [0, 0]),
   le("Pega HTML", UI, [{"keyName": "slug", "condition": "eq", "keyValue": "app"}], [224, 0]),
   responde("Serve", "={{ $json.html }}", [448, 0], texto=True,
            cabecalhos={"Content-Type": "text/html; charset=utf-8",
                        "Cache-Control": "no-store"}),
 ],
 "connections": liga(("Abre", "Pega HTML"), ("Pega HTML", "Serve")),
}

# ─────────────────────────────────────────────── API
JS_ROTEIA = """const SENHA = %s;
const b = $json.body || {};
if (b.senha !== SENHA) return [{ json: { ok: false, erro: 'senha recusada', http: 401 } }];

const acao = String(b.acao || '');
if (['entrar','criar','pedidos','entregues','lista'].indexOf(acao) < 0)
  return [{ json: { ok: false, erro: 'ação desconhecida', http: 400 } }];

const digitos = String(b.cnpj || '').replace(/[^0-9]/g, '');
let filtro = String(b.filtro || '');
const planilha = String(b.planilha_b64 || '');

if (acao === 'criar') {
  if (!String(b.cliente || '').trim())
    return [{ json: { ok: false, erro: 'diga para qual cliente é a lista', http: 400 } }];
  if (!filtro && !planilha)
    return [{ json: { ok: false, erro: 'sem filtro e sem planilha', http: 400 } }];
  if (filtro) {
    // O teto de 2 CNAEs vale no servidor. A tela é conveniência, não regra.
    let f;
    try { f = JSON.parse(filtro); }
    catch (e) { return [{ json: { ok: false, erro: 'filtro inválido', http: 400 } }]; }
    if ((f.cnaes || []).length > 2)
      return [{ json: { ok: false, erro: 'no máximo 2 CNAEs', http: 400 } }];
  }
}
// Arredonda para múltiplo de 100: toda lista entregue tem no máximo 100
// empresas, e isso é constante do produto, não configuração do cliente.
const bruto = Number(b.total) || 100;
const total = Math.min(10000, Math.max(100, Math.ceil(bruto / 100) * 100));

return [{ json: {
  ok: true, acao: acao,
  raiz: digitos.slice(0, 8) || '___nenhum___',
  // A chave da lista a abrir na tela. Sentinela quando nao e esta a acao,
  // para o no de leitura nao arrastar um arquivo a toa.
  chave: acao === 'lista' ? String(b.chave || '').slice(0, 120) : '___nenhuma___',
  cliente: String(b.cliente || '').trim().slice(0, 80),
  filtro: filtro, planilha_nome: String(b.planilha_nome || '').slice(0, 120),
  planilha_b64: planilha, total: total,
  // Enriquecimento deixou de ser opcao em 12/11: toda lista roda o
  // pipeline inteiro. O teto de US$ 5 por lista e a trava que sobra.
  com_apify: 'sim',
  pedido_id: 'p-' + Date.now().toString(36) + '-' +
             Math.random().toString(36).slice(2, 7),
  criado_em: new Date().toISOString()
} }];""" % json.dumps(SENHA)

JS_MONTA = """const r = $('Roteia').first().json;
const limpa = function (nome) {
  return $(nome).all().map(function (i) { return i.json; })
                .filter(function (x) { return x && x.id !== undefined; });
};
if (r.acao === 'entrar') return [{ json: { ok: true } }];

if (r.acao === 'lista') {
  // Abre na tela a MESMA lista que foi entregue: o CSV guardado aqui, nao
  // uma segunda consulta a base. O que a pessoa ve e o que ela baixa.
  const arq = limpa('Lê arquivo').filter(function (a) { return a.b64; })[0];
  if (!arq) return [{ json: { ok: false, erro: 'lista não encontrada ou já expirada' } }];

  const ASPA = String.fromCharCode(34);
  const NL = String.fromCharCode(10);
  const CR = String.fromCharCode(13);

  let texto = Buffer.from(String(arq.b64), 'base64').toString('utf8');
  if (texto.charCodeAt(0) === 65279) texto = texto.slice(1);   // BOM do Excel

  // CSV com ponto e virgula, campos entre aspas, aspas dobradas por escape.
  const linhas = [];
  let campo = '', atual = [], dentro = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (dentro) {
      if (c === ASPA) {
        if (texto[i + 1] === ASPA) { campo += ASPA; i++; } else { dentro = false; }
      } else { campo += c; }
    } else if (c === ASPA) { dentro = true; }
    else if (c === ';') { atual.push(campo); campo = ''; }
    else if (c === NL) { atual.push(campo); linhas.push(atual); atual = []; campo = ''; }
    else if (c !== CR) { campo += c; }
  }
  if (campo !== '' || atual.length) { atual.push(campo); linhas.push(atual); }
  if (!linhas.length) return [{ json: { ok: false, erro: 'lista vazia' } }];

  const cab = linhas.shift();
  // So as colunas que valem numa tela. A planilha baixada continua com as 61.
  const QUER = ['CNPJ', 'Razão Social', 'Nome Fantasia', 'Contatos', 'E-mail',
                'Instagram', 'Site', 'Cidade', 'Estado', 'CNAE', 'Atividade',
                'Já Entregue?', 'Entregue Antes Em'];
  const idx = [];
  QUER.forEach(function (nome) {
    const i = cab.indexOf(nome);
    if (i >= 0) idx.push({ i: i, nome: nome });
  });

  const corpo = [];
  linhas.forEach(function (l) {
    if (!l.join('').trim()) return;
    corpo.push(idx.map(function (x) {
      return l[x.i] === undefined ? '' : l[x.i];
    }));
  });
  return [{ json: { ok: true, total: corpo.length,
                    colunas: idx.map(function (x) { return x.nome; }),
                    linhas: corpo } }];
}

const listas = limpa('Lê listas').filter(function (l) { return l.chave; });
const porPedido = {};
listas.forEach(function (l) {
  (porPedido[l.pedido_id] = porPedido[l.pedido_id] || []).push({
    chave: l.chave, fatia: Number(l.fatia), formato: l.formato,
    empresas: Number(l.empresas || 0), repetidas: Number(l.repetidas || 0) });
});

const pedidos = limpa('Lê pedidos').filter(function (p) { return p.pedido_id; })
  .sort(function (a, b) { return String(b.criado_em).localeCompare(String(a.criado_em)); })
  .slice(0, 30)
  .map(function (p) {
    // planilha_b64 NÃO sai daqui: é a entrada, pode ter megabytes, e a tela
    // não tem o que fazer com ela.
    return { pedido_id: p.pedido_id, cliente: p.cliente, status: p.status,
             filtro: p.filtro, total: Number(p.total || 0), motivo: p.motivo,
             planilha_nome: p.planilha_nome, criado_em: p.criado_em,
             // andamento ao vivo, empurrado pela ponte a cada 15s
             processadas: Number(p.processadas || 0),
             listas_prontas: Number(p.listas_prontas || 0),
             listas: Number(p.listas || 0),
             listas: (porPedido[p.pedido_id] || []).sort(function (a, b) {
               return a.fatia - b.fatia ||
                      String(a.formato).localeCompare(String(b.formato)); }) };
  });
return [{ json: { ok: true, pedidos: pedidos } }];"""

apiwf = {
 "name": "Prospecção · API",
 "settings": {"executionOrder": "v1"},
 "nodes": [
   webhook("Pede", "POST", "prospeccao-api", [0, 0]),
   codigo("Roteia", JS_ROTEIA, [224, 0]),
   se("Autorizado?", "={{ $json.ok }}", [448, 0]),
   se("É criar?", "={{ $json.acao === 'criar' }}", [672, -120]),
   no("Cria pedido", "dataTable", 1.1, [896, -220], {
     "resource": "row", "operation": "insert", "dataTableId": PEDIDOS,
     "columns": {"mappingMode": "defineBelow", "value": {
       "pedido_id": "={{ $json.pedido_id }}", "status": "pendente",
       "filtro": "={{ $json.filtro }}", "total": "={{ $json.total }}",
       "formatos": "xlsx,csv",
       "planilha_nome": "={{ $json.planilha_nome }}",
       "planilha_b64": "={{ $json.planilha_b64 }}",
       "cliente": "={{ $json.cliente }}",
       "com_apify": "={{ $json.com_apify }}",
       "teto_usd": 5,
       "criado_em": "={{ $json.criado_em }}"}}}),
   responde("Criado", "={{ { ok: true, pedido_id: $('Roteia').first().json.pedido_id } }}",
            [1120, -220]),
   # "todas as linhas": a Data Table não aceita notEquals na leitura, então
   # a condição sempre-verdadeira é a data ser posterior ao ano 2000.
   le("Lê pedidos", PEDIDOS,
      [{"keyName": "criado_em", "condition": "gt",
        "keyValue": "2000-01-01T00:00:00.000Z"}], [896, 0]),
   le("Lê listas", LISTAS,
      [{"keyName": "criado_em", "condition": "gt",
        "keyValue": "2000-01-01T00:00:00.000Z"}], [1120, 0], True),
   le("Lê entregues", ENTREGUES,
      [{"keyName": "raiz", "condition": "eq",
        "keyValue": "={{ $('Roteia').first().json.raiz }}"}], [1344, 0], True),
   le("Lê arquivo", ARQUIVOS,
      [{"keyName": "chave", "condition": "eq",
        "keyValue": "={{ $('Roteia').first().json.chave }}"}], [1568, 0], True),
   codigo("Monta", JS_MONTA, [1792, 0]),
   responde("Responde", "={{ $json }}", [2016, 0]),
   responde("Negado", "={{ { erro: $json.erro } }}", [672, 120],
            "={{ $json.http || 401 }}"),
 ],
 "connections": (lambda c: (liga_se(c, "Autorizado?", "É criar?", "Negado"),
                            liga_se(c, "É criar?", "Cria pedido", "Lê pedidos"), c)[-1])(
   liga(("Pede", "Roteia"), ("Roteia", "Autorizado?"),
        ("Cria pedido", "Criado"), ("Lê pedidos", "Lê listas"),
        ("Lê listas", "Lê entregues"), ("Lê entregues", "Lê arquivo"),
        ("Lê arquivo", "Monta"), ("Monta", "Responde"))),
}

# ─────────────────────────────────────────────── publica
def publicar(wf):
    existente = workflow(wf["name"])
    corpo = {"name": wf["name"], "nodes": wf["nodes"],
             "connections": wf["connections"], "settings": wf["settings"]}
    if existente:
        if existente["active"]:
            api(f"/workflows/{existente['id']}/deactivate", "POST")
        api(f"/workflows/{existente['id']}", "PUT", corpo)
        wid = existente["id"]
        acao = "atualizado"
    else:
        r = api("/workflows", "POST", corpo)
        wid = r["id"]
        acao = "criado"
    # Workflow criado pela API cai no projeto pessoal; Data Table é por
    # projeto, então sem a transferência o nó não acha a tabela.
    # O GET de um workflow devolve homeProject nulo; o projeto está em shared.
    w = api(f"/workflows/{wid}")
    compart = (w.get("shared") or [{}])[0]
    atual = compart.get("projectId") or (w.get("homeProject") or {}).get("id")
    if atual != PROJETO:
        api(f"/workflows/{wid}/transfer", "PUT", {"destinationProjectId": PROJETO})
    api(f"/workflows/{wid}/activate", "POST")
    print(f"  {acao} e ativo: {wf['name']}  {wid}")
    return wid

if __name__ == "__main__":
    quais = sys.argv[1:] or ["guardar", "baixar", "limpar", "app", "api"]
    todos = {"guardar": guardar, "baixar": baixar, "limpar": limpar,
             "app": app, "api": apiwf}
    for k in quais:
        publicar(todos[k])
