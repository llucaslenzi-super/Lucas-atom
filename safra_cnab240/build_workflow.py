"""
Gera o codigo SDK do workflow 'Agente Boletos Safra' com o safra_cnab240.js
embutido inline no Code node "Safra Router".

O workflow tem:
  - 5 webhooks (safra-emitir, safra-consultar, safra-alterar, safra-baixar, safra-processar-retorno)
  - 5 Set (Normalize) - cada um adiciona action
  - Todos apontam pro mesmo Code "Safra Router" (que roda o safra_cnab240.js + switch)
  - Router -> Respond to Webhook

Simulacao pura: nao escreve em Data Table nem chama HTTP. Devolve o payload que
seria enfileirado / processado. Prod bloqueado por default.
"""
import os
import json

AQUI = os.path.dirname(os.path.abspath(__file__))
LIB_JS_PATH = os.path.join(AQUI, "safra_cnab240.js")

with open(LIB_JS_PATH) as f:
    LIB_JS = f.read()

# Router - roda apos a lib. Le input, roteia por action, devolve resultado.
ROUTER = r'''
// ====== ROUTER SAFRA ======
// Recebe items com { action, env, payload } vindos do Normalize.
// Devolve items com { ok, action, env, resultado } pro Respond.

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
  SISTEMA_SAFRA: '7',
};

const results = [];
for (const item of $input.all()) {
  const body = item.json;
  const action = String(body.action || '').toLowerCase();
  const env = String(body.env || 'sandbox').toLowerCase();

  // PROD bloqueado por default. Retorna erro claro se tentar.
  if (env === 'prod' || env === 'production') {
    results.push({
      json: {
        ok: false,
        action,
        env,
        erro: 'PROD_BLOQUEADO',
        mensagem: 'Emissao em producao esta bloqueada. Use env=sandbox pra homologacao.',
      },
    });
    continue;
  }

  let resultado;
  try {
    if (action === 'emitir') {
      // Simula emissao: gera REM de entrada, devolve conteudo + CB + LD
      const titulos = body.titulos || [];
      if (!titulos.length) throw new Error('titulos vazio');
      const rem = gerarRemessaEntrada(CFG, titulos, body.seq_arquivo || 1, new Date());
      const boletos = [];
      for (const t of titulos) {
        const cb = codigoBarras44(CFG, t.nosso_numero, t.data_vencimento, t.valor_centavos);
        const ld = linhaDigitavel(cb);
        boletos.push({ nosso_numero: t.nosso_numero, cb, ld });
      }
      resultado = {
        rem_bytes: rem.length,
        rem_linhas: rem.split('\r\n').filter(l => l).length,
        boletos,
        // conteudo_rem: rem,   // omitido no default - pode ser gigante
      };
      if (body.include_rem_content) resultado.conteudo_rem = rem;

    } else if (action === 'consultar') {
      // Simula consulta - devolve status "SIMULADO" (real leria Data Table)
      const nn = String(body.nosso_numero || '').padStart(9, '0');
      resultado = {
        nosso_numero: nn,
        status: 'SIMULADO',
        mensagem: 'Consulta real leria Data Table safra_titulos_gerados',
      };

    } else if (action === 'alterar' || action === 'alterar_venc' || action === 'alterar_dados') {
      // Simula alteracao - devolve REM que seria enfileirado
      const titulos = body.titulos || [];
      if (!titulos.length) throw new Error('titulos vazio');
      const fn = action === 'alterar_venc' ? gerarRemessaAlteracaoVenc : gerarRemessaAlteracaoDados;
      const rem = fn(CFG, titulos, body.seq_arquivo || 1, new Date());
      resultado = {
        codigo_movimento: action === 'alterar_venc' ? '06' : '31',
        rem_bytes: rem.length,
        rem_linhas: rem.split('\r\n').filter(l => l).length,
      };
      if (body.include_rem_content) resultado.conteudo_rem = rem;

    } else if (action === 'baixar') {
      const titulos = body.titulos || [];
      if (!titulos.length) throw new Error('titulos vazio');
      const rem = gerarRemessaBaixa(CFG, titulos, body.seq_arquivo || 1, new Date());
      resultado = {
        codigo_movimento: '02',
        rem_bytes: rem.length,
        rem_linhas: rem.split('\r\n').filter(l => l).length,
      };
      if (body.include_rem_content) resultado.conteudo_rem = rem;

    } else if (action === 'processar_retorno' || action === 'retorno') {
      // Parse do .RET vindo em body.conteudo_ret (string) ou body.conteudo_base64
      let conteudo = body.conteudo_ret;
      if (!conteudo && body.conteudo_base64) {
        conteudo = Buffer.from(body.conteudo_base64, 'base64').toString('latin1');
      }
      if (!conteudo) throw new Error('falta conteudo_ret ou conteudo_base64');
      const parsed = parseRetorno(conteudo);
      resultado = {
        header_arquivo: parsed.header_arquivo,
        qtd_eventos: parsed.eventos.length,
        eventos: parsed.eventos.map(e => classificarEvento(e)),
        trailer_lote: parsed.trailer_lote,
        trailer_arquivo: parsed.trailer_arquivo,
        erros_parse: parsed.erros_parse,
      };

    } else {
      throw new Error('action desconhecida: ' + action);
    }

    results.push({ json: { ok: true, action, env, resultado } });
  } catch (e) {
    results.push({ json: { ok: false, action, env, erro: String(e.message || e) } });
  }
}
return results;
'''

# Escapa a lib pra ficar dentro de um template string SDK-friendly
# SDK proibe backtick, mas jsCode e string qualquer. Vamos usar aspas duplas
# no SDK code e escapar backticks/${} pra preservar template literals dentro
# da lib.
FULL_JS = LIB_JS + "\n\n" + ROUTER

# Escapa aspas simples, backslashes, newlines pra virar string SDK
def escape_for_sdk_single_quote(s):
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")

# Alternativa mais legivel: usar JSON.stringify pra construir a string
FULL_JS_JSON = json.dumps(FULL_JS)  # produz uma string JS valida entre aspas duplas

# Constroi o workflow SDK code
WF = '''import { workflow, node, trigger, merge, expr } from '@n8n/workflow-sdk';

const CODE = ''' + FULL_JS_JSON + ''';

const webhookEmitir = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Emitir',
    parameters: {
      path: 'safra-emitir',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'emitir' } }],
});

const webhookConsultar = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Consultar',
    parameters: {
      path: 'safra-consultar',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'consultar' } }],
});

const webhookAlterar = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Alterar',
    parameters: {
      path: 'safra-alterar',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'alterar_venc' } }],
});

const webhookBaixar = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Baixar',
    parameters: {
      path: 'safra-baixar',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'baixar' } }],
});

const webhookRetorno = trigger({
  type: 'n8n-nodes-base.webhook',
  version: 2.1,
  config: {
    name: 'Webhook Processar Retorno',
    parameters: {
      path: 'safra-processar-retorno',
      httpMethod: 'POST',
      responseMode: 'responseNode',
      options: {},
    },
  },
  output: [{ body: { action: 'processar_retorno' } }],
});

const normalizeEmitir = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Emitir',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'emitir', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'titulos', name: 'titulos', value: expr("{{ $json.body?.titulos ?? [] }}"), type: 'array' },
          { id: 'seq_arquivo', name: 'seq_arquivo', value: expr("{{ $json.body?.seq_arquivo ?? 1 }}"), type: 'number' },
          { id: 'include_rem_content', name: 'include_rem_content', value: expr("{{ $json.body?.include_rem_content ?? false }}"), type: 'boolean' },
        ],
      },
    },
  },
  output: [{ action: 'emitir', env: 'sandbox', titulos: [], seq_arquivo: 1, include_rem_content: false }],
});

const normalizeConsultar = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Consultar',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'consultar', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'nosso_numero', name: 'nosso_numero', value: expr("{{ $json.body?.nosso_numero ?? '' }}"), type: 'string' },
        ],
      },
    },
  },
  output: [{ action: 'consultar', env: 'sandbox', nosso_numero: '' }],
});

const normalizeAlterar = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Alterar',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: expr("{{ $json.body?.action ?? 'alterar_venc' }}"), type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'titulos', name: 'titulos', value: expr("{{ $json.body?.titulos ?? [] }}"), type: 'array' },
          { id: 'seq_arquivo', name: 'seq_arquivo', value: expr("{{ $json.body?.seq_arquivo ?? 1 }}"), type: 'number' },
          { id: 'include_rem_content', name: 'include_rem_content', value: expr("{{ $json.body?.include_rem_content ?? false }}"), type: 'boolean' },
        ],
      },
    },
  },
  output: [{ action: 'alterar_venc', env: 'sandbox', titulos: [], seq_arquivo: 1, include_rem_content: false }],
});

const normalizeBaixar = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Baixar',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'baixar', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'titulos', name: 'titulos', value: expr("{{ $json.body?.titulos ?? [] }}"), type: 'array' },
          { id: 'seq_arquivo', name: 'seq_arquivo', value: expr("{{ $json.body?.seq_arquivo ?? 1 }}"), type: 'number' },
          { id: 'include_rem_content', name: 'include_rem_content', value: expr("{{ $json.body?.include_rem_content ?? false }}"), type: 'boolean' },
        ],
      },
    },
  },
  output: [{ action: 'baixar', env: 'sandbox', titulos: [], seq_arquivo: 1, include_rem_content: false }],
});

const normalizeRetorno = node({
  type: 'n8n-nodes-base.set',
  version: 3.5,
  config: {
    name: 'Normalize Retorno',
    parameters: {
      mode: 'manual',
      includeOtherFields: false,
      assignments: {
        assignments: [
          { id: 'action', name: 'action', value: 'processar_retorno', type: 'string' },
          { id: 'env', name: 'env', value: expr("{{ $json.body?.env ?? 'sandbox' }}"), type: 'string' },
          { id: 'conteudo_ret', name: 'conteudo_ret', value: expr("{{ $json.body?.conteudo_ret ?? '' }}"), type: 'string' },
          { id: 'conteudo_base64', name: 'conteudo_base64', value: expr("{{ $json.body?.conteudo_base64 ?? '' }}"), type: 'string' },
        ],
      },
    },
  },
  output: [{ action: 'processar_retorno', env: 'sandbox', conteudo_ret: '', conteudo_base64: '' }],
});

const codeRouter = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Safra Router',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: CODE,
    },
  },
  output: [{ ok: true, action: 'emitir', env: 'sandbox', resultado: {} }],
});

const respond = node({
  type: 'n8n-nodes-base.respondToWebhook',
  version: 1.5,
  config: {
    name: 'Respond',
    parameters: {
      respondWith: 'json',
      responseBody: expr("{{ JSON.stringify($json) }}"),
      options: { responseCode: 200 },
    },
  },
});

export default workflow('agente-boletos-safra', 'Agente Boletos Safra')
  .add(webhookEmitir).to(normalizeEmitir).to(codeRouter).to(respond)
  .add(webhookConsultar).to(normalizeConsultar).to(codeRouter)
  .add(webhookAlterar).to(normalizeAlterar).to(codeRouter)
  .add(webhookBaixar).to(normalizeBaixar).to(codeRouter)
  .add(webhookRetorno).to(normalizeRetorno).to(codeRouter);
'''

out_path = os.path.join(AQUI, "workflow_agente_safra.js")
with open(out_path, "w") as f:
    f.write(WF)
print(f"Gerado: {out_path}  ({len(WF)} bytes)")
