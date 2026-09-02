/**
 * Teste bit-a-bit Python vs JS pra TODOS os fluxos:
 *   1. Entrada (cod 01) - 3 titulos
 *   2. Baixa (cod 02)
 *   3. Alteracao vencimento (cod 06)
 *   4. Alteracao dados (cod 31)
 *   5. Parse retorno .RET
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const M = require('./safra_cnab240.js');

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

const hoje = new Date();
hoje.setUTCHours(0, 0, 0, 0);
const addDias = (d, n) => { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; };

const TITULOS = [
  {
    nosso_numero: '000000001', seu_numero: 'TESTE00001', especie: '02',
    valor_centavos: 10000, data_emissao: hoje, data_vencimento: addDias(hoje, 30),
    juros_codigo: '1', juros_data: addDias(hoje, 31), juros_valor_centavos: 10,
    multa_codigo: '2', multa_data: addDias(hoje, 31), multa_percentual: 2.00,
    desconto_codigo: '0', desconto_data: addDias(hoje, 30), desconto_valor_centavos: 0,
    protesto_codigo: '3', protesto_dias: 0, baixa_codigo: '1', baixa_dias: 60,
    pagador: {
      tipo_inscricao: '1', cpf_cnpj: '52998224725',
      nome: 'JOSE DA SILVA TESTE', endereco: 'RUA DAS FLORES 100',
      bairro: 'CENTRO', cep_prefixo: '55190', cep_sufixo: '505',
      cidade: 'SANTA CRUZ DO CAPIBAR', uf: 'PE',
    },
  },
  {
    nosso_numero: '000000002', seu_numero: 'TESTE00002', especie: '02',
    valor_centavos: 50000, data_emissao: hoje, data_vencimento: addDias(hoje, 45),
    juros_codigo: '1', juros_data: addDias(hoje, 46), juros_valor_centavos: 10,
    multa_codigo: '2', multa_data: addDias(hoje, 46), multa_percentual: 2.00,
    desconto_codigo: '0', desconto_data: addDias(hoje, 45), desconto_valor_centavos: 0,
    protesto_codigo: '3', protesto_dias: 0, baixa_codigo: '1', baixa_dias: 60,
    pagador: {
      tipo_inscricao: '1', cpf_cnpj: '31628382821',
      nome: 'MARIA APARECIDA TESTE', endereco: 'AV DEZESSETE DE AGOSTO 500 APT 302',
      bairro: 'CASA FORTE', cep_prefixo: '52061', cep_sufixo: '540',
      cidade: 'RECIFE', uf: 'PE',
    },
  },
  {
    nosso_numero: '000000003', seu_numero: 'TESTE00003', especie: '02',
    valor_centavos: 123456, data_emissao: hoje, data_vencimento: addDias(hoje, 60),
    juros_codigo: '1', juros_data: addDias(hoje, 61), juros_valor_centavos: 41,
    multa_codigo: '2', multa_data: addDias(hoje, 61), multa_percentual: 2.00,
    desconto_codigo: '1', desconto_data: addDias(hoje, 60), desconto_valor_centavos: 5000,
    protesto_codigo: '3', protesto_dias: 0, baixa_codigo: '1', baixa_dias: 90,
    pagador: {
      tipo_inscricao: '2', cpf_cnpj: '45283163000167',
      nome: 'CONFECCOES TESTE HOMOLOG LTDA', endereco: 'RUA DA PAZ 2000 GALPAO 4',
      bairro: 'VILA MADALENA', cep_prefixo: '05436', cep_sufixo: '060',
      cidade: 'SAO PAULO', uf: 'SP',
    },
  },
];

const outDir = path.join(__dirname, 'output');
fs.mkdirSync(outDir, { recursive: true });

function pyGerar(func) {
  // Gera o REM Python correspondente e retorna o conteudo
  const script = `
import sys
sys.path.insert(0, '${__dirname}')
from cnab240 import ${func}
from titulos import TITULOS
print(${func}(TITULOS), end='')
`;
  return execSync(`python3 -c "${script.replace(/"/g, '\\"')}"`, {
    encoding: 'utf8', cwd: __dirname,
  });
}

function diffFirstLine(a, b, label) {
  const la = a.split('\r\n');
  const lb = b.split('\r\n');
  const n = Math.max(la.length, lb.length);
  for (let i = 0; i < n; i++) {
    if (la[i] !== lb[i]) {
      console.log(`  DIFF na linha ${i + 1}:`);
      console.log(`    JS: [${la[i]}]`);
      console.log(`    PY: [${lb[i]}]`);
      for (let j = 0; j < Math.max((la[i] || '').length, (lb[i] || '').length); j++) {
        if ((la[i] || '')[j] !== (lb[i] || '')[j]) {
          console.log(`    primeiro char diff pos ${j + 1}: JS="${(la[i] || '')[j]}" PY="${(lb[i] || '')[j]}"`);
          break;
        }
      }
      return false;
    }
  }
  return true;
}

const casos = [
  { nome: 'ENTRADA (01)', jsFn: 'gerarRemessaEntrada', pyFn: 'gerar_remessa_entrada' },
  { nome: 'BAIXA (02)', jsFn: 'gerarRemessaBaixa', pyFn: 'gerar_remessa_baixa' },
  { nome: 'ALT VENC (06)', jsFn: 'gerarRemessaAlteracaoVenc', pyFn: 'gerar_remessa_alteracao_venc' },
  { nome: 'ALT DADOS (31)', jsFn: 'gerarRemessaAlteracaoDados', pyFn: 'gerar_remessa_alteracao_dados' },
  { nome: 'PROTESTO (09)', jsFn: 'gerarRemessaProtesto', pyFn: 'gerar_remessa_protesto' },
  { nome: 'SUSTAR PROT (10)', jsFn: 'gerarRemessaSustarProtesto', pyFn: 'gerar_remessa_sustar_protesto' },
];

let todosOk = true;
console.log('=== Teste bit-a-bit Python vs JS - remessas ===\n');
for (const c of casos) {
  const remJs = M[c.jsFn](CFG, TITULOS, 1, hoje);
  const remPy = pyGerar(c.pyFn);
  fs.writeFileSync(path.join(outDir, `TEST_${c.jsFn}_JS.REM`), remJs);
  fs.writeFileSync(path.join(outDir, `TEST_${c.jsFn}_PY.REM`), remPy);
  const ok = remJs === remPy;
  if (ok) {
    console.log(`  ${c.nome.padEnd(20)} OK (bit-a-bit)`);
  } else {
    console.log(`  ${c.nome.padEnd(20)} DIFERE`);
    diffFirstLine(remJs, remPy, c.nome);
    todosOk = false;
  }
}

console.log('\n=== Teste parser retorno JS ===\n');
const retFile = path.join(outDir, 'SAMPLE_RETORNO.RET');
if (!fs.existsSync(retFile)) {
  console.log(`  Falta gerar sample retorno: python3 retorno_gerar_sample.py`);
  todosOk = false;
} else {
  const conteudo = fs.readFileSync(retFile, 'utf8');
  const r = M.parseRetorno(conteudo);
  console.log(`  Eventos parseados: ${r.eventos.length}`);
  for (const ev of r.eventos) {
    const c = M.classificarEvento(ev);
    const motivos = c.motivos_rejeicao.map(m => `${m.codigo}`).join(',') || '-';
    console.log(`    NN ${c.nosso_numero.padStart(3)}  ${c.status.padStart(10)}  oc ${c.ocorrencia}  pago R$ ${(c.valor_pago_centavos / 100).toFixed(2).padStart(10)}  motivos: ${motivos}`);
  }
  const okEventos = r.eventos.length === 3;
  const okStatus = r.eventos.map(e => M.classificarEvento(e).status);
  const esperado = ['CONFIRMADO', 'LIQUIDADO', 'REJEITADO'];
  const ok = okEventos && JSON.stringify(okStatus) === JSON.stringify(esperado);
  if (ok) console.log('  OK - status batem: CONFIRMADO, LIQUIDADO, REJEITADO');
  else {
    console.log(`  FAIL - status: ${JSON.stringify(okStatus)}, esperado ${JSON.stringify(esperado)}`);
    todosOk = false;
  }
}

console.log('\n=== Resultado final ===');
console.log(todosOk ? 'TUDO OK' : 'ALGO FALHOU');
process.exit(todosOk ? 0 : 1);
