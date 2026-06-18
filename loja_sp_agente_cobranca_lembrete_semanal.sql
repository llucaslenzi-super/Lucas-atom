-- Agente de Lembrete de Cobrança Semanal Loja SP
-- Output: nekt_trusted.loja_sp_agente_cobranca_lembrete_semanal
-- Schedule: manual
-- Folder: loja_sp_cobranca
-- Diferença vs Gaspar: pedido vem direto da string 'Pedido(s): N1,N2...' em
-- mssql_loja_sp_dbo_nota_fiscal_capa.observacoes. JOIN por CR.documento = NF.documentoorigem.
-- NÃO usa fatura_itens.

WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
janela AS (
  SELECT data_execucao,
    data_execucao AS data_inicio,
    CASE date_format(data_execucao, '%a')
      WHEN 'Fri' THEN date_add('day', 3, data_execucao)
      ELSE date_add('day', 2, data_execucao)
    END AS data_fim
  FROM params
),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento,
    TRY_CAST(cr.documento AS BIGINT) AS doc_int
  FROM nekt_raw.mssql_loja_sp_dbo_cr_documentos cr
  CROSS JOIN janela j
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 70, 3, 7, 68)
    AND CAST(cr.datavencimento AS DATE) BETWEEN j.data_inicio AND j.data_fim
),
pedidos_por_titulo AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    MAX(regexp_extract(nf.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)) AS pedidos_str
  FROM titulos t
  JOIN nekt_raw.mssql_loja_sp_dbo_nota_fiscal_capa nf
    ON TRY_CAST(nf.documentoorigem AS BIGINT) = t.doc_int
   AND nf.origemnota = 'Fatura'
  WHERE regexp_like(nf.observacoes, 'Pedido\(s\):')
  GROUP BY t.codcliente, t.tipodocumento, t.documento, t.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento,
    CASE
      WHEN t.tipodocumento IN (3, 68) THEN
        'Cheque ' || t.documento || ' / venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
      WHEN ppt.pedidos_str IS NOT NULL AND ppt.pedidos_str <> '' THEN
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento || ' / Ped.' || ppt.pedidos_str
      ELSE
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento
    END AS linha_mensagem
  FROM titulos t
  LEFT JOIN pedidos_por_titulo ppt
    ON ppt.codcliente = t.codcliente AND ppt.tipodocumento = t.tipodocumento
   AND ppt.documento = t.documento AND ppt.parcela = t.parcela
),
clientes_clean AS (
  SELECT c.codcliente,
    regexp_replace(c.nome, '[\r\n\t]', ' ') AS nome,
    c.telefone AS telefone_raw,
    regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '') AS telefone_digitos
  FROM nekt_raw.mssql_loja_sp_dbo_clientes c
),
agg AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    array_join(array_agg(l.linha_mensagem), chr(10)) AS linhas_msg
  FROM linhas l GROUP BY l.codcliente
)
SELECT
  'SP' AS filial,
  cc.codcliente, cc.nome,
  cc.telefone_raw AS telefone,
  cc.telefone_digitos,
  CASE
    WHEN cc.telefone_digitos = '' THEN 'SEM CONTATO'
    WHEN LENGTH(cc.telefone_digitos) < 10 THEN 'CONTATO INVALIDO'
    WHEN LENGTH(cc.telefone_digitos) IN (10, 11) THEN 'OK'
    WHEN LENGTH(cc.telefone_digitos) IN (12, 13) AND SUBSTR(cc.telefone_digitos, 1, 2) = '55' THEN 'OK'
    ELSE 'CONTATO INVALIDO'
  END AS status_contato,
  a.qtd_titulos, a.valor_total,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Lembrete, nesta semana você tem vencimento(s) para:' || chr(10) || chr(10)
   || a.linhas_msg AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM agg a
JOIN clientes_clean cc ON cc.codcliente = a.codcliente
ORDER BY a.valor_total DESC
