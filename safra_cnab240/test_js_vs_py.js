/**
 * Roda o gerador JS com os mesmos titulos do Python, exporta REM.
 * Depois compara bit-a-bit com o REM gerado pelo Python.
 */

const fs = require('fs');
const path = require('path');
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

// Mesmos titulos do titulos.py (data igual a hoje pra bater)
const hoje = new Date();
hoje.setUTCHours(0, 0, 0, 0);
const addDias = (d, n) => { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; };

const TITULOS = [
  {
    nosso_numero: '000000001',
    seu_numero: 'TESTE00001',
    especie: '02',
    valor_centavos: 10000,
    data_emissao: hoje,
    data_vencimento: addDias(hoje, 30),
    juros_codigo: '1',
    juros_data: addDias(hoje, 31),
    juros_valor_centavos: 10,
    desconto_codigo: '0',
    desconto_data: addDias(hoje, 30),
    desconto_valor_centavos: 0,
    protesto_codigo: '3',
    protesto_dias: 0,
    baixa_codigo: '1',
    baixa_dias: 60,
    pagador: {
      tipo_inscricao: '1', cpf_cnpj: '52998224725',
      nome: 'JOSE DA SILVA TESTE', endereco: 'RUA DAS FLORES 100',
      bairro: 'CENTRO', cep_prefixo: '55190', cep_sufixo: '505',
      cidade: 'SANTA CRUZ DO CAPIBAR', uf: 'PE',
    },
  },
  {
    nosso_numero: '000000002',
    seu_numero: 'TESTE00002',
    especie: '02',
    valor_centavos: 50000,
    data_emissao: hoje,
    data_vencimento: addDias(hoje, 45),
    juros_codigo: '1',
    juros_data: addDias(hoje, 46),
    juros_valor_centavos: 10,
    desconto_codigo: '0',
    desconto_data: addDias(hoje, 45),
    desconto_valor_centavos: 0,
    protesto_codigo: '3',
    protesto_dias: 0,
    baixa_codigo: '1',
    baixa_dias: 60,
    pagador: {
      tipo_inscricao: '1', cpf_cnpj: '31628382821',
      nome: 'MARIA APARECIDA TESTE', endereco: 'AV DEZESSETE DE AGOSTO 500 APT 302',
      bairro: 'CASA FORTE', cep_prefixo: '52061', cep_sufixo: '540',
      cidade: 'RECIFE', uf: 'PE',
    },
  },
  {
    nosso_numero: '000000003',
    seu_numero: 'TESTE00003',
    especie: '02',
    valor_centavos: 123456,
    data_emissao: hoje,
    data_vencimento: addDias(hoje, 60),
    juros_codigo: '1',
    juros_data: addDias(hoje, 61),
    juros_valor_centavos: 41,
    desconto_codigo: '1',
    desconto_data: addDias(hoje, 60),
    desconto_valor_centavos: 5000,
    protesto_codigo: '3',
    protesto_dias: 0,
    baixa_codigo: '1',
    baixa_dias: 90,
    pagador: {
      tipo_inscricao: '2', cpf_cnpj: '45283163000167',
      nome: 'CONFECCOES TESTE HOMOLOG LTDA', endereco: 'RUA DA PAZ 2000 GALPAO 4',
      bairro: 'VILA MADALENA', cep_prefixo: '05436', cep_sufixo: '060',
      cidade: 'SAO PAULO', uf: 'SP',
    },
  },
];

const rem = M.gerarRemessa(CFG, TITULOS, 1, hoje);
const outJs = path.join(__dirname, 'output', 'SOUL_INDUST_355_TESTE_JS.REM');
fs.writeFileSync(outJs, rem);
console.log('JS -> ' + outJs);

// Comparar com REM do Python
const remPy = fs.readFileSync(path.join(__dirname, 'output', 'SOUL_INDUST_355_TESTE.REM'), 'utf8');
if (rem === remPy) {
  console.log('OK - JS == Python (bit-a-bit)');
} else {
  console.log('DIFERENCA:');
  const lJs = rem.split('\r\n');
  const lPy = remPy.split('\r\n');
  for (let i = 0; i < Math.max(lJs.length, lPy.length); i++) {
    if (lJs[i] !== lPy[i]) {
      console.log('Linha ' + (i+1) + ':');
      console.log('  JS: [' + lJs[i] + ']');
      console.log('  PY: [' + lPy[i] + ']');
      // Encontra primeira diferenca de char
      for (let j = 0; j < Math.max((lJs[i] || '').length, (lPy[i] || '').length); j++) {
        if ((lJs[i] || '')[j] !== (lPy[i] || '')[j]) {
          console.log('  Primeira diff na pos ' + (j+1) + ': JS="' + (lJs[i] || '')[j] + '" PY="' + (lPy[i] || '')[j] + '"');
          break;
        }
      }
    }
  }
}

// Testar CB + LD de cada titulo
console.log('\nCB + LD dos 3 titulos:');
for (const t of TITULOS) {
  const cb = M.codigoBarras44(CFG, t.nosso_numero, t.data_vencimento, t.valor_centavos);
  const ld = M.linhaDigitavel(cb);
  console.log('  NN ' + t.nosso_numero + ': CB=' + cb + ' LD=' + ld);
}
