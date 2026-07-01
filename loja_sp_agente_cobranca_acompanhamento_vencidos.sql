-- Agente de Acompanhamento de Cobrança de Vencidos Loja SP
-- Output: nekt_trusted.loja_sp_agente_cobranca_acompanhamento_vencidos
-- Schedule: manual
-- Folder: loja_sp_cobranca
-- Régua: saldo > 0, tipo IN (10, 80, 3, 7, 68, 5),
--        vencidos entre 2 e 180 dias.
-- Ciclos: 1 = 2 dias / 2 = 3-10 / 3 = 11-180.
-- Formato da mensagem:
--   *CATEGORIA:*
--   venc. dd/mm/yyyy / Valor: R$ ... / Doc.NNN (linhas em ordem cronológica ASC)
--   ...linha branca...
--   *PROXIMA_CATEGORIA:* ...

WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento,
    date_diff('day', CAST(cr.datavencimento AS DATE), p.data_execucao) AS dias_vencido,
    TRY_CAST(cr.documento AS BIGINT) AS doc_int,
    CASE cr.tipodocumento
      WHEN 10 THEN 'BOLETO'
      WHEN 80 THEN 'PIX'
      WHEN 3  THEN 'CHEQUE'
      WHEN 68 THEN 'CHEQUE'
      WHEN 7  THEN 'CREDIÁRIO'
      WHEN 5  THEN 'CREDIÁRIO'
    END AS tipo_doc_nome
  FROM nekt_raw.mssql_loja_sp_dbo_cr_documentos cr
  CROSS JOIN params p
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 3, 7, 68, 5)
    AND CAST(cr.datavencimento AS DATE) BETWEEN date_add('day', -180, p.data_execucao) AND date_add('day', -2, p.data_execucao)
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
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento, t.dias_vencido,
    t.tipo_doc_nome,
    CASE WHEN t.dias_vencido = 2 THEN 1
         WHEN t.dias_vencido BETWEEN 3 AND 10 THEN 2
         ELSE 3 END AS ciclo,
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
  FROM nekt_raw.mssql_loja_sp_dbo_clientes c
),
ciclos_por_cliente AS (
  SELECT codcliente, ciclo, COUNT(*) AS qtd
  FROM linhas GROUP BY codcliente, ciclo
),
ciclo_predominante AS (
  SELECT codcliente, ciclo,
    ROW_NUMBER() OVER (PARTITION BY codcliente ORDER BY qtd DESC, ciclo DESC) AS rn
  FROM ciclos_por_cliente
),
tipos_por_cliente AS (
  SELECT codcliente,
    array_join(array_agg(DISTINCT tipo_doc_nome ORDER BY tipo_doc_nome ASC), ', ') AS documentos
  FROM linhas GROUP BY codcliente
),
metricas AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    MAX(l.dias_vencido) AS dias_vencido_max
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
  m.qtd_titulos, m.valor_total,
  tpc.documentos,
  'Ciclo ' || CAST(cp.ciclo AS VARCHAR) AS ciclo_predominante,
  m.dias_vencido_max,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || '🚨 *VENCIMENTOS EM ABERTO* 🚨' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Verificamos que ficou pendente:' || chr(10) || chr(10)
   || ma.linhas_msg || chr(10) || chr(10)
   || 'Caso já tenha efetuado pagamento favor desconsiderar esta mensagem. 😉' AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM metricas m
JOIN clientes_clean cc ON cc.codcliente = m.codcliente
JOIN ciclo_predominante cp ON cp.codcliente = m.codcliente AND cp.rn = 1
JOIN tipos_por_cliente tpc ON tpc.codcliente = m.codcliente
JOIN mensagem_agg ma ON ma.codcliente = m.codcliente
ORDER BY m.dias_vencido_max DESC, m.valor_total DESC
