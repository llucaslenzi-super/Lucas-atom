const fs=require('fs');
// ---- users ----
const U=[
 {u:'diretoria@soultextil.com.br',n:'Lucas Lenzi',a:'Diretoria',p:'admin',m:'claude-opus-5-5',dom:'DIR',w:14},
 {u:'joao@soultextil.com.br',n:'João Meurer',a:'Diretoria',p:'gestor',m:'claude-opus-5-5',dom:'DIRC',w:10},
 {u:'natasha@soultextil.com.br',n:'Natasha Wildi',a:'Diretoria',p:'gestor',m:'claude-opus-5-5',dom:'DIRO',w:10},
 {u:'thiago@soultextil.com.br',n:'Thiago Bonetti',a:'Diretoria',p:'gestor',m:'claude-opus-5-5',dom:'DIRF',w:10},
 {u:'paulo@soultextil.com.br',n:'Paulo Deschamps',a:'Diretoria',p:'gestor',m:'claude-opus-5-5',dom:'DIRI',w:10},
 {u:'industrial@soultextil.com.br',n:'Luiz Fontana',a:'Industrial',p:'operacional',m:'claude-sonnet-5',dom:'IND',w:14},
 {u:'financeiro@soultextil.com.br',n:'Max Speroni',a:'Financeiro',p:'operacional',m:'claude-sonnet-5',dom:'FIN',w:14},
 {u:'comercial1@soultextil.com.br',n:'Fernanda Souza',a:'Comercial',p:'operacional',m:'claude-sonnet-5',dom:'COM',w:9},
 {u:'pcp1@soultextil.com.br',n:'Rafael Lima',a:'PCP',p:'operacional',m:'claude-sonnet-5',dom:'IND',w:9},
 {u:'qualidade1@soultextil.com.br',n:'Ivi Constante',a:'Qualidade',p:'operacional',m:'claude-haiku-4-5-20251001',dom:'QUA',w:8},
 {u:'comercial2@soultextil.com.br',n:'Bruno Carvalho',a:'Comercial',p:'operacional',m:'claude-sonnet-5',dom:'COM',w:7},
 {u:'financeiro2@soultextil.com.br',n:'Camila Rocha',a:'Financeiro',p:'operacional',m:'claude-opus-5-5',dom:'FIN',w:9},
 {u:'industrial2@soultextil.com.br',n:'Anderson Dias',a:'Industrial',p:'operacional',m:'claude-sonnet-5',dom:'IND',w:7},
 {u:'logistica1@soultextil.com.br',n:'Patrícia Gomes',a:'Logística',p:'operacional',m:'claude-haiku-4-5-20251001',dom:'LOG',w:7},
 {u:'compras1@soultextil.com.br',n:'Diego Fernandes',a:'Compras',p:'operacional',m:'claude-sonnet-5',dom:'COMP',w:7},
 {u:'pcp2@soultextil.com.br',n:'Larissa Ribeiro',a:'PCP',p:'operacional',m:'claude-haiku-4-5-20251001',dom:'IND',w:6},
 {u:'comercial3@soultextil.com.br',n:'Thiago Almeida',a:'Comercial',p:'gestor',m:'claude-opus-5-5',dom:'COMG',w:8},
 {u:'ti1@soultextil.com.br',n:'Gustavo Nunes',a:'TI',p:'admin',m:'claude-sonnet-5',dom:'TI',w:6},
];
// ---- rng ----
let S=987654321; function rnd(){S=(S*1103515245+12345)&0x7fffffff;return S/0x7fffffff;}
function ri(a,b){return Math.floor(a+rnd()*(b-a+1));}
function pick(arr){return arr[Math.floor(rnd()*arr.length)];}
function money(v){return v.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});}
function kg(v){return v.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});}
function v(base,pct){return base*(1+(rnd()*2-1)*pct);}
// ---- content templates by domain ----
const PROD=[['1502002','Malha Dry Pes Mescla'],['1401118','Malha PV Dry Fio Tinto'],['1503047','Malha Piquet Algodão'],['1602210','Ribana 1x1 Penteada'],['1305126','Meia Malha 30/1 Penteada']];
const CLI=[['10482','Lojas Havan'],['20915','Riachuelo'],['30877','Renner'],['11540','Malwee'],['22371','Pernambucanas']];
const FILIAL=[['Filial PE (MATRIZ)',9.97e6,0.62],['Filial SP (LOJASP)',4.27e6,0.27],['Gaspar (SC)',1.79e6,0.11]];
function faturamento(){
  var pe=v(9972618,0.08),sp=v(4266853,0.10),sc=v(1786325,0.12);var tot=pe+sp+sc;
  var vol=v(293561,0.07);
  return {prompt:pick(['Qual foi o faturamento dos últimos 30 dias por filial?','Faturamento do mês por filial, por favor','Como está o faturamento por filial neste mês?']),
    fonte:'ERP · Faturamento (faturas unificadas)',
    resp:'# Faturamento — últimos 30 dias por filial\n\n| Filial | Faturamento (R$) | Volume (kg) | Part. |\n|---|---:|---:|---:|\n| Filial PE (MATRIZ) | '+money(pe)+' | '+kg(vol*0.63)+' | '+(pe/tot*100).toFixed(1)+'% |\n| Filial SP (LOJASP) | '+money(sp)+' | '+kg(vol*0.24)+' | '+(sp/tot*100).toFixed(1)+'% |\n| Gaspar (SC) | '+money(sc)+' | '+kg(vol*0.13)+' | '+(sc/tot*100).toFixed(1)+'% |\n| **Total** | **'+money(tot)+'** | **'+kg(vol)+'** | **100%** |\n\nA **Filial PE (MATRIZ)** segue como principal origem do faturamento no período. Volume total faturado de **'+kg(vol)+' kg**.'};
}
function titulos(){
  var a=v(842000,0.15),b=v(415000,0.2),c=v(228000,0.25),d=v(160000,0.3);var t=a+b+c+d;
  return {prompt:pick(['Títulos vencidos em aberto','Quais os títulos vencidos em aberto hoje?','Me mostra o aging de títulos vencidos']),
    fonte:'ERP · Contas a Receber',
    resp:'# Títulos vencidos em aberto\n\n| Faixa de atraso | Valor (R$) | Títulos |\n|---|---:|---:|\n| 1–30 dias | '+money(a)+' | '+ri(58,92)+' |\n| 31–60 dias | '+money(b)+' | '+ri(30,50)+' |\n| 61–90 dias | '+money(c)+' | '+ri(15,28)+' |\n| > 90 dias | '+money(d)+' | '+ri(8,18)+' |\n| **Total** | **'+money(t)+'** | **'+ri(120,180)+'** |\n\nMaior concentração na faixa **1–30 dias**. Recomendo priorizar a régua de cobrança dos títulos acima de 90 dias ('+money(d)+').'};
}
function contasPagar(){
  var t=v(1180000,0.15);
  return {prompt:pick(['Contas a pagar dos próximos 15 dias','O que temos de contas a pagar até o dia 15?','Contas a pagar da quinzena']),
    fonte:'ERP · Contas a Pagar',
    resp:'# Contas a pagar — próximos 15 dias\n\n| Categoria | Valor (R$) |\n|---|---:|\n| Fornecedores de fio | '+money(t*0.44)+' |\n| Energia e utilidades | '+money(t*0.14)+' |\n| Impostos e tributos | '+money(t*0.22)+' |\n| Serviços e terceiros | '+money(t*0.20)+' |\n| **Total** | **'+money(t)+'** |\n\nMaior desembolso concentrado em **fornecedores de fio**. Fluxo de caixa comporta o período sem necessidade de antecipação.'};
}
function contasReceber(){
  var t=v(2340000,0.12);
  return {prompt:pick(['Contas a receber a vencer nos próximos 15 dias','Previsão de recebimento da quinzena','Quanto temos a receber até o fim do mês?']),
    fonte:'ERP · Contas a Receber',
    resp:'# Contas a receber a vencer — 15 dias\n\n| Filial | A receber (R$) |\n|---|---:|\n| Filial PE (MATRIZ) | '+money(t*0.6)+' |\n| Filial SP (LOJASP) | '+money(t*0.27)+' |\n| Gaspar (SC) | '+money(t*0.13)+' |\n| **Total** | **'+money(t)+'** |\n\nEntrada prevista de **'+money(t)+'** no período, concentrada na matriz.'};
}
function estoqueProd(){
  var pr=pick(PROD);var livre=v(18.81,0.6),res=v(517.71,0.4);var tot=livre+res;
  return {prompt:'Qual o estoque disponível do produto '+pr[0]+'?',
    fonte:'ERP · Estoque (peças, qualidade A)',
    resp:'Para o produto **'+pr[0]+' – '+pr[1]+'**:\n\n| Situação | kg | Peças |\n|---|---:|---:|\n| Livre | '+kg(livre)+' | '+ri(1,4)+' |\n| Reservado | '+kg(res)+' | '+ri(20,34)+' |\n| **Total** | **'+kg(tot)+'** | **'+ri(24,38)+'** |\n\n**Disponível (livre): '+kg(livre)+' kg** — '+(livre/tot*100).toFixed(2)+'% do total. O restante está reservado para pedidos em carteira.'};
}
function fios(){
  var f1=v(12480,0.2),f2=v(9310,0.2),f3=v(7120,0.25),f4=v(5640,0.25);
  return {prompt:pick(['Fios com maior saldo em kg','Quais fios têm maior saldo em estoque?','Ranking de fios por saldo em kg']),
    fonte:'ERP · Estoque de fios',
    resp:'# Fios com maior saldo (kg)\n\n| Fio | Saldo (kg) |\n|---|---:|\n| 30/1 penteado | '+kg(f1)+' |\n| 26/1 cardado | '+kg(f2)+' |\n| 20/1 penteado | '+kg(f3)+' |\n| Poliéster 30/1 | '+kg(f4)+' |\n\nO **fio 30/1 penteado** lidera o saldo. Cobertura confortável para a programação de tecelagem da próxima semana.'};
}
function producao(){
  var kgt=v(9840,0.18);
  return {prompt:pick(['Produção da tecelagem hoje em kg','Quanto a tecelagem produziu hoje?','Produção do dia na tecelagem']),
    fonte:'ERP · PCP (produção tecelagem)',
    resp:'# Produção da tecelagem — hoje\n\n| Setor | Produzido (kg) | Meta (kg) | Atingido |\n|---|---:|---:|---:|\n| Tecelagem circular | '+kg(kgt*0.7)+' | '+kg(kgt*0.72)+' | '+(97+rnd()*4).toFixed(0)+'% |\n| Tecelagem retilínea | '+kg(kgt*0.3)+' | '+kg(kgt*0.30)+' | '+(98+rnd()*3).toFixed(0)+'% |\n| **Total** | **'+kg(kgt)+'** | — | — |\n\nProdução dentro da meta do dia. Sem paradas relevantes registradas.'};
}
function cobertura(){
  return {prompt:pick(['Cobertura de fios para as OPs em curso','Temos fio suficiente para as OPs abertas?','Cobertura de fios das ordens em curso']),
    fonte:'ERP · PCP + Estoque de fios',
    resp:'# Cobertura de fios — OPs em curso\n\n| OP | Necessidade (kg) | Saldo (kg) | Cobertura |\n|---|---:|---:|---:|\n| OP-'+ri(4100,4300)+' | '+kg(v(1240,0.2))+' | '+kg(v(1600,0.2))+' | '+(110+ri(0,25))+'% |\n| OP-'+ri(4100,4300)+' | '+kg(v(980,0.2))+' | '+kg(v(760,0.2))+' | '+(70+ri(0,20))+'% |\n| OP-'+ri(4100,4300)+' | '+kg(v(1520,0.2))+' | '+kg(v(1980,0.2))+' | '+(115+ri(0,20))+'% |\n\nUma OP está **abaixo de 100%** de cobertura — sugiro antecipar a compra do fio correspondente para não travar a programação.'};
}
function opsAbertas(){
  return {prompt:pick(['Ordens de produção abertas na tecelagem','Quantas OPs abertas temos na tecelagem?','OPs em aberto na tecelagem']),
    fonte:'ERP · PCP (ordens de produção)',
    resp:'Há **'+ri(28,44)+' OPs abertas** na tecelagem no momento:\n\n| Status | OPs | Volume (kg) |\n|---|---:|---:|\n| Em produção | '+ri(12,20)+' | '+kg(v(14200,0.2))+' |\n| Aguardando fio | '+ri(4,9)+' | '+kg(v(4200,0.3))+' |\n| Aguardando programação | '+ri(6,12)+' | '+kg(v(6100,0.3))+' |\n\nO gargalo atual é **aguardando fio** — vale alinhar com Compras.'};
}
function leadtime(){
  return {prompt:pick(['Lead time médio da tinturaria','Qual o lead time da tinturaria hoje?','Tempo médio de tinturaria']),
    fonte:'ERP · PCP (tinturaria)',
    resp:'O **lead time médio da tinturaria** nos últimos 30 dias é de **'+(4.2+rnd()*1.6).toFixed(1)+' dias**.\n\n| Etapa | Dias (média) |\n|---|---:|\n| Fila de entrada | '+(1.4+rnd()).toFixed(1)+' |\n| Processo de tingimento | '+(1.8+rnd()*0.6).toFixed(1)+' |\n| Acabamento/revisão | '+(1.1+rnd()*0.5).toFixed(1)+' |\n\nO maior tempo está na **fila de entrada** — priorização por cor ajudaria a reduzir.'};
}
function reprovacao(){
  return {prompt:pick(['Taxa de reprovação por máquina','Reprovação por máquina neste mês','Qual máquina está reprovando mais?']),
    fonte:'ERP · Qualidade',
    resp:'# Taxa de reprovação por máquina — mês\n\n| Máquina | Reprovação | Produção (kg) |\n|---|---:|---:|\n| Circular 12 | '+(1.2+rnd()*0.8).toFixed(1)+'% | '+kg(v(3200,0.2))+' |\n| Circular 07 | '+(2.4+rnd()*1.2).toFixed(1)+'% | '+kg(v(2900,0.2))+' |\n| Retilínea 03 | '+(0.8+rnd()*0.6).toFixed(1)+'% | '+kg(v(1500,0.2))+' |\n\nA **Circular 07** está acima da média — recomendo inspeção de agulhas e tensão.'};
}
function defeitos(){
  var pr=pick(PROD);
  return {prompt:'Defeitos classe B do produto '+pr[0]+' no mês',
    fonte:'ERP · Qualidade',
    resp:'Para **'+pr[0]+' – '+pr[1]+'** no mês:\n\n| Classe | Peças | kg | % |\n|---|---:|---:|---:|\n| A (aprovado) | '+ri(180,240)+' | '+kg(v(3400,0.15))+' | '+(94+rnd()*3).toFixed(1)+'% |\n| B (defeito) | '+ri(8,20)+' | '+kg(v(190,0.3))+' | '+(3+rnd()*2).toFixed(1)+'% |\n\nPrincipais causas de classe B: **furos** e **barramento**. Dentro do limite de controle do produto.'};
}
function reclamacoes(){
  return {prompt:pick(['Reclamações abertas de qualidade','Temos reclamações de qualidade em aberto?','Reclamações de qualidade pendentes']),
    fonte:'ERP · Qualidade (atendimento)',
    resp:'Há **'+ri(3,9)+' reclamações de qualidade abertas**:\n\n| Cliente | Motivo | Status |\n|---|---|---|\n| '+pick(CLI)[1]+' | Diferença de tonalidade | Em análise |\n| '+pick(CLI)[1]+' | Furo em peça | Aguardando amostra |\n| '+pick(CLI)[1]+' | Gramatura fora de faixa | Em tratativa |\n\nNenhuma reclassificada como crítica. SLA de resposta médio de '+ri(2,5)+' dias.'};
}
function topClientes(){
  return {prompt:pick(['Top 10 clientes por volume no último trimestre','Quais os maiores clientes por volume?','Ranking de clientes por volume no trimestre']),
    fonte:'ERP · Clientes + Pedidos',
    resp:'# Top clientes por volume — trimestre\n\n| # | Cliente | Volume (kg) |\n|---|---|---:|\n| 1 | '+CLI[1][1]+' | '+kg(v(48200,0.15))+' |\n| 2 | '+CLI[2][1]+' | '+kg(v(41500,0.15))+' |\n| 3 | '+CLI[3][1]+' | '+kg(v(33800,0.15))+' |\n| 4 | '+CLI[0][1]+' | '+kg(v(27600,0.15))+' |\n| 5 | '+CLI[4][1]+' | '+kg(v(21400,0.15))+' |\n\nOs cinco maiores concentram cerca de **'+ri(58,68)+'%** do volume do trimestre.'};
}
function pedidosCliente(){
  var cl=pick(CLI);
  return {prompt:'Quais pedidos em aberto do cliente '+cl[0]+'?',
    fonte:'ERP · Pedidos',
    resp:'Pedidos em aberto — **'+cl[1]+' (cód. '+cl[0]+')**:\n\n| Pedido | Itens | Volume (kg) | Status |\n|---|---:|---:|---|\n| '+ri(90000,99999)+' | '+ri(3,9)+' | '+kg(v(2400,0.3))+' | Em produção |\n| '+ri(90000,99999)+' | '+ri(2,6)+' | '+kg(v(1600,0.3))+' | Aguardando faturamento |\n| '+ri(90000,99999)+' | '+ri(1,4)+' | '+kg(v(900,0.3))+' | Separação |\n\nTotal em aberto: **'+kg(v(4900,0.2))+' kg**. Um pedido já está pronto para faturar.'};
}
function ficha(){
  return {prompt:pick(['Ficha técnica da malha PV Dry','Me passa a ficha técnica da PV Dry','Composição e gramatura da malha PV Dry']),
    fonte:'ERP · Fichas Técnicas',
    resp:'# Ficha técnica — Malha PV Dry\n\n| Atributo | Valor |\n|---|---|\n| Composição | 67% poliéster / 33% viscose |\n| Gramatura | '+ri(150,175)+' g/m² |\n| Largura útil | '+(1.6+rnd()*0.2).toFixed(2)+' m |\n| Rendimento | '+(3.4+rnd()*0.4).toFixed(2)+' m/kg |\n| Acabamento | Dry fit / antiodor |\n\nIndicada para vestuário esportivo. Fio recomendado: poliéster 30/1 + viscose 30/1.'};
}
function expedicao(){
  return {prompt:pick(['Pedidos prontos para expedição','O que está pronto para expedir hoje?','Pedidos liberados para expedição']),
    fonte:'ERP · Pedidos (expedição)',
    resp:'# Pedidos prontos para expedição\n\n| Pedido | Cliente | Volume (kg) | Transportadora |\n|---|---|---:|---|\n| '+ri(90000,99999)+' | '+pick(CLI)[1]+' | '+kg(v(2100,0.3))+' | Jamef |\n| '+ri(90000,99999)+' | '+pick(CLI)[1]+' | '+kg(v(1400,0.3))+' | TNT |\n| '+ri(90000,99999)+' | '+pick(CLI)[1]+' | '+kg(v(980,0.3))+' | Braspress |\n\nTotal liberado: **'+kg(v(4500,0.2))+' kg** em '+ri(3,7)+' pedidos.'};
}
function volumeExp(){
  return {prompt:pick(['Volume expedido na semana','Quanto expedimos esta semana?','Expedição da semana em kg']),
    fonte:'ERP · Pedidos (expedição)',
    resp:'Volume expedido na semana: **'+kg(v(38400,0.15))+' kg** em '+ri(40,70)+' pedidos.\n\n| Dia | Expedido (kg) |\n|---|---:|\n| Seg | '+kg(v(7200,0.2))+' |\n| Ter | '+kg(v(8100,0.2))+' |\n| Qua | '+kg(v(7600,0.2))+' |\n| Qui | '+kg(v(8400,0.2))+' |\n| Sex | '+kg(v(7100,0.2))+' |\n\nSem atrasos relevantes de coleta.'};
}
function comprasFio(){
  return {prompt:pick(['Pedidos de compra de fio em aberto','Quais compras de fio estão em aberto?','Ordens de compra de fio pendentes']),
    fonte:'ERP · Compras + Estoque',
    resp:'# Pedidos de compra de fio em aberto\n\n| OC | Fornecedor | Fio | kg | Previsão |\n|---|---|---|---:|---|\n| '+ri(7000,7999)+' | Fiação Coteminas | 30/1 penteado | '+kg(v(4200,0.2))+' | '+ri(3,12)+' dias |\n| '+ri(7000,7999)+' | Fiasul | 26/1 cardado | '+kg(v(3100,0.2))+' | '+ri(3,12)+' dias |\n\nTotal em aberto: **'+kg(v(7300,0.2))+' kg**. Nenhuma OC atrasada além do prazo combinado.'};
}
function fornecedores(){
  return {prompt:pick(['Fornecedores com entrega atrasada','Algum fornecedor está atrasado?','Fornecedores em atraso de entrega']),
    fonte:'ERP · Compras',
    resp:'Fornecedores com entrega em atraso:\n\n| Fornecedor | OC | Atraso | Item |\n|---|---|---:|---|\n| Fiasul | '+ri(7000,7999)+' | '+ri(2,8)+' dias | Fio 26/1 |\n| Química Têxtil SC | '+ri(7000,7999)+' | '+ri(1,5)+' dias | Corante reativo |\n\n'+ri(2,4)+' OCs em atraso. Recomendo acionar o comercial dos fornecedores e revisar o estoque de segurança do fio 26/1.'};
}
function adocaoIA(){
  return {prompt:pick(['Adoção de IA por setor','Como está a adoção da IA por setor?','Uso da plataforma de IA por área']),
    fonte:'Plataforma Soul · uso interno',
    resp:'# Adoção da plataforma por setor\n\n| Setor | Usuários ativos | Consultas/mês |\n|---|---:|---:|\n| Financeiro | '+ri(2,4)+' | '+ri(80,160)+' |\n| Industrial/PCP | '+ri(3,6)+' | '+ri(120,220)+' |\n| Comercial | '+ri(2,5)+' | '+ri(90,180)+' |\n| Diretoria | '+ri(3,5)+' | '+ri(60,120)+' |\n\nAdoção crescente, com maior uso em **Industrial/PCP**. Próximo passo: onboarding de Logística e Compras.'};
}
function consolidado(){
  var g=v(16025796,0.06);
  return {prompt:pick(['Faturamento consolidado do grupo','Qual o faturamento consolidado do grupo?','Consolidado de faturamento do grupo no mês']),
    fonte:'ERP · Faturamento (consolidado)',
    resp:'# Faturamento consolidado do grupo — mês\n\n| Indicador | Valor |\n|---|---:|\n| Faturamento bruto | R$ '+money(g)+' |\n| Volume total | '+kg(v(293561,0.06))+' kg |\n| Ticket médio | R$ '+money(g/ri(1100,1300))+' |\n| Margem bruta estimada | '+(30+rnd()*6).toFixed(1)+'% |\n\nCrescimento em linha com o planejado para o período. Matriz PE segue como principal origem.'};
}
function margem(){
  return {prompt:pick(['Margem por filial neste mês','Qual a margem bruta por filial?','Rentabilidade por filial']),
    fonte:'ERP · Faturamento + Custos',
    resp:'# Margem bruta por filial — mês\n\n| Filial | Margem bruta |\n|---|---:|\n| Filial PE (MATRIZ) | '+(32+rnd()*5).toFixed(1)+'% |\n| Filial SP (LOJASP) | '+(28+rnd()*5).toFixed(1)+'% |\n| Gaspar (SC) | '+(30+rnd()*5).toFixed(1)+'% |\n\nMatriz PE mantém a melhor margem, puxada por mix de produtos de maior valor agregado.'};
}
function usoTI(){
  return {prompt:pick(['Usuários ativos no mês','Quantos usuários ativos temos na plataforma?','Uso da plataforma por área']),
    fonte:'Plataforma Soul · uso interno',
    resp:'# Uso da plataforma — mês\n\n| Métrica | Valor |\n|---|---:|\n| Usuários ativos | '+ri(12,17)+' |\n| Consultas | '+ri(380,520)+' |\n| Custo total de IA | R$ '+money(v(2.9,0.3))+' |\n| Bloqueios por escopo | '+ri(4,9)+' |\n\nGovernança operando: todas as interações auditadas e PII mascarada antes do modelo.'};
}
// scope block (Industrial/PCP/Qualidade/Logística/Compras asking R$)
function bloqueio(area){
  var msg;
  if(area==='Industrial'||area==='PCP')msg='Essa consulta está fora do seu perfil de acesso ('+area+'). Seu perfil consulta estoque, produção, PCP, fios, pedidos e qualidade — em **kg e %**. Valores financeiros (R$) não estão liberados para o seu perfil. Se precisar desse dado, solicite acesso pela tela de Configurações.';
  else if(area==='Qualidade')msg='Essa consulta está fora do seu perfil de acesso (Qualidade). Seu perfil consulta indicadores de qualidade, fichas técnicas e estoque — em kg e %. Faturamento em R$ não está liberado para o seu perfil.';
  else msg='Essa consulta está fora do seu perfil de acesso ('+area+'). Faturamento em R$ não está liberado para o seu perfil. Solicite acesso pela tela de Configurações se necessário.';
  return {prompt:pick(['Qual o faturamento em R$ deste mês?','Quanto faturamos em reais este mês?','Me mostra o faturamento em R$ por filial']),
    fonte:'Fora de escopo', alerta:'fora_escopo', resp:msg};
}
// domain -> template pool
function tpl(dom,area){
  if(dom==='FIN')return pick([faturamento,titulos,contasPagar,contasReceber,titulos,faturamento])();
  if(dom==='IND')return pick([estoqueProd,fios,producao,cobertura,opsAbertas,leadtime,estoqueProd,fios])();
  if(dom==='QUA')return pick([reprovacao,defeitos,reclamacoes,estoqueProd])();
  if(dom==='COM')return pick([topClientes,pedidosCliente,ficha,pedidosCliente])();
  if(dom==='COMG')return pick([topClientes,pedidosCliente,faturamento,ficha])();
  if(dom==='LOG')return pick([expedicao,volumeExp,expedicao])();
  if(dom==='COMP')return pick([comprasFio,fornecedores,comprasFio])();
  if(dom==='TI')return pick([usoTI,adocaoIA])();
  if(dom==='DIR')return pick([consolidado,faturamento,adocaoIA,margem,topClientes,titulos])();
  if(dom==='DIRC')return pick([topClientes,faturamento,pedidosCliente,consolidado])();
  if(dom==='DIRO')return pick([producao,opsAbertas,cobertura,reprovacao,expedicao])();
  if(dom==='DIRF')return pick([faturamento,titulos,contasPagar,contasReceber,margem,consolidado])();
  if(dom==='DIRI')return pick([producao,fios,estoqueProd,opsAbertas,cobertura])();
  return faturamento();
}
function cost(m,ti,to){if(m.indexOf('opus')>=0)return 3+rnd()*13;if(m.indexOf('haiku')>=0)return 0.08+rnd()*0.5;return 0.6+rnd()*4;}
// ---- uids existentes (para sobrescrever sem duplicar a tabela) ----
var REPO='/home/user/Lucas-atom/plataforma-soul/seeds/interacoes_seed.json';
var EXIST=[];try{EXIST=require(REPO).map(function(r){return r.uid;});}catch(e){}
// ---- generate ----
const START=new Date('2026-05-01T11:00:00Z').getTime();
const END=new Date('2026-09-24T20:00:00Z').getTime();
const SPAN=END-START;
let rows=[];let cseq=0;
U.forEach(function(us){
  var nConv=Math.max(7,Math.round(us.w*1.9));
  for(var c=0;c<nConv;c++){
    var _mo=[5,6,7,8,9][Math.floor(rnd()*5)];var _md=(_mo===9?24:28);var day=Date.UTC(2026,_mo-1,1+Math.floor(rnd()*_md),8+Math.floor(rnd()*11),Math.floor(rnd()*60),0);
    var conv='c-'+us.u.split('@')[0]+'-'+(cseq++);
    var nmsg=ri(1,4);
    for(var k=0;k<nmsg;k++){
      var t=new Date(day+k*ri(40,300)*1000).toISOString();
      var canBlock=(['Industrial','PCP','Qualidade','Logística','Compras'].indexOf(us.a)>=0);
      var block=canBlock&&rnd()<0.14&&k===0;
      var T=block?bloqueio(us.a):tpl(us.dom,us.a);
      var ti=block?ri(700,1600):ri(2600,16000),to=block?ri(60,160):ri(260,1100);
      rows.push({
        criado_em:t, usuario:us.u, area:us.a, perfil:us.p, modelo:us.m,
        tokens_in:ti, tokens_out:to, custo:block?cost(us.m,ti,to)*0.3:cost(us.m,ti,to),
        prompt:T.prompt, resposta:T.resp, guardrails:'[]', alerta:T.alerta||'',
        fonte:T.fonte, conversa_id:conv, ip:'', dispositivo:'',
        feedback: rnd()<0.16?'up':(rnd()<0.04?'down':'')
      });
    }
  }
});
rows.sort(function(a,b){return new Date(a.criado_em)-new Date(b.criado_em);});
// ---- escala custo por mês para R$700-900 ----
var byM={};rows.forEach(function(r){var m=String(r.criado_em).slice(0,7);(byM[m]=byM[m]||[]).push(r);});
Object.keys(byM).forEach(function(m){var arr=byM[m];var sum=0;arr.forEach(function(r){sum+=r.custo;});var target=700+rnd()*200;var f=sum>0?target/sum:1;arr.forEach(function(r){r.custo=+(r.custo*f).toFixed(4);});});
// ---- uid: reaproveita existentes (overwrite) + novos para o excedente ----
rows.forEach(function(r,i){ r.uid = (i<EXIST.length)? EXIST[i] : ('g3-'+(i-EXIST.length)); });
fs.writeFileSync(REPO,JSON.stringify(rows));
var mm={};rows.forEach(function(r){var k=String(r.criado_em).slice(0,7);if(!mm[k])mm[k]={n:0,c:0};mm[k].n++;mm[k].c+=r.custo;});
console.log('total',rows.length,'| overwrite',Math.min(rows.length,EXIST.length),'| novos',Math.max(0,rows.length-EXIST.length));
Object.keys(mm).sort().forEach(function(k){console.log(k,mm[k].n,'int · R$',mm[k].c.toFixed(2));});
var blk=rows.filter(function(r){return r.alerta==='fora_escopo';}).length;console.log('blocks',blk);
