-- Agente de Lembrete de Cobrança (A Vencer) Matriz PE
-- Output: nekt_trusted.matriz_agente_cobranca_lembrete_semanal
-- Schedule: cron 30 8 * * 1,3,5 (seg/qua/sex 8:30 BRT)
-- Folder: matriz_cobranca
-- Régua: saldo > 0, tipo IN (10, 80, 3, 7, 68, 5),
--        janela: hoje+1 até (Sex → +3 / demais → +2).
--   Seg roda → ter+qua ; Qua roda → qui+sex ; Sex roda → sáb+dom+seg
-- SEM CICLOS (ciclos só existem no fluxo de Vencidos).
-- Extração de pedido (PE): CR.documento = NF.documentoorigem, regex em NF.observacoes.
-- Formato da mensagem:
--   *CATEGORIA:*
--   venc. dd/mm/yyyy / Valor: R$ ... / Doc.NNN (linhas em ordem cronológica ASC)
--   ...linha branca...
--   *PROXIMA_CATEGORIA:* ...

WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
janela AS (
  SELECT data_execucao,
    date_add('day', 1, data_execucao) AS data_inicio,
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
    TRY_CAST(cr.documento AS BIGINT) AS doc_int,
    CASE cr.tipodocumento
      WHEN 10 THEN 'BOLETO'
      WHEN 80 THEN 'PIX'
      WHEN 3  THEN 'CHEQUE'
      WHEN 68 THEN 'CHEQUE'
      WHEN 7  THEN 'CREDIÁRIO'
      WHEN 5  THEN 'CREDIÁRIO'
    END AS tipo_doc_nome
  FROM nekt_raw.mssql_matriz_dbo_cr_documentos cr
  CROSS JOIN janela j
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 3, 7, 68, 5)
    AND CAST(cr.datavencimento AS DATE) BETWEEN j.data_inicio AND j.data_fim
),
pedidos_por_titulo AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    MAX(regexp_extract(nf.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)) AS pedidos_str
  FROM titulos t
  JOIN nekt_raw.mssql_matriz_dbo_nota_fiscal_capa nf
    ON TRY_CAST(nf.documentoorigem AS BIGINT) = t.doc_int
   AND nf.origemnota = 'Fatura'
  WHERE regexp_like(nf.observacoes, 'Pedido\(s\):')
  GROUP BY t.codcliente, t.tipodocumento, t.documento, t.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento,
    t.tipo_doc_nome,
    CASE
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
  FROM nekt_raw.mssql_matriz_dbo_clientes c
),
tipos_por_cliente AS (
  SELECT codcliente,
    array_join(array_agg(DISTINCT tipo_doc_nome ORDER BY tipo_doc_nome ASC), ', ') AS documentos
  FROM linhas GROUP BY codcliente
),
metricas AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total
  FROM linhas l GROUP BY l.codcliente
),
blocos_por_tipo AS (
  SELECT codcliente, tipo_doc_nome,
    array_join(
      array_agg(linha_mensagem ORDER BY datavencimento ASC, documento ASC),
      chr(10)
    ) AS bloco
  FROM linhas
  GROUP BY codcliente, tipo_doc_nome
),
mensagem_agg AS (
  SELECT codcliente,
    array_join(
      array_agg(
        '*' || tipo_doc_nome || ':*' || chr(10) || bloco
        ORDER BY tipo_doc_nome ASC
      ),
      chr(10) || chr(10)
    ) AS linhas_msg
  FROM blocos_por_tipo
  GROUP BY codcliente
)
SELECT
  'PE' AS filial,
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
  m.qtd_titulos, m.valor_total,
  tpc.documentos,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || '🚨 *TÍTULOS A VENCER* 🚨' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Lembrete, nos próximos dias você tem vencimento(s) para:' || chr(10) || chr(10)
   || ma.linhas_msg || chr(10) || chr(10)
   || 'Caso já tenha efetuado pagamento favor desconsiderar esta mensagem. 😉' AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM metricas m
JOIN clientes_clean cc ON cc.codcliente = m.codcliente
JOIN tipos_por_cliente tpc ON tpc.codcliente = m.codcliente
JOIN mensagem_agg ma ON ma.codcliente = m.codcliente
ORDER BY m.valor_total DESC
