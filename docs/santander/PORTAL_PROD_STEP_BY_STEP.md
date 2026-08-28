# Portal Santander Developer — Criar app produção passo a passo

> Quando você tentou, travou. Vamos com clique-por-clique. Se travar em algum passo específico me diz qual e a mensagem exata.

URL: **https://developer.santander.com.br**

Login: mesma conta que criou a app sandbox `sc api Santander boletos`.

---

## 1. Confirmar que está logado na conta certa

- Canto superior direito deve mostrar seu email
- Se pedir login, entra com o mesmo email que abriu a app sandbox
- Se não lembrar qual foi: as apps sandbox e prod ficam na MESMA conta — abre `My Applications` e veja o app sandbox atual (`sc api Santander boletos`) lá. Se você vê, tá na conta certa.

## 2. My Applications → Create Application

- Menu superior → **My Applications** (às vezes aparece como "My Apps")
- Botão azul **Create Application** (canto superior direito da listagem)

Se aparecer opção **Sandbox** vs **Production**: escolha **Production**.

Se não aparecer essa escolha (portal antigo): você cria a app "normal" e o campo de ambiente vem no formulário abaixo — procure por `Environment` ou `Ambiente` = Production.

## 3. Preencher formulário da app

| Campo | Valor |
|---|---|
| Application name | `soul-boletos-prod` (ou similar; livre) |
| Description | `Emissao de boletos Soul Textil - convenio 0028697 - Gaspar SC` |
| Environment | **Production** |
| Redirect URI (se pedir) | Pode deixar `https://soultextil.app.n8n.cloud` |
| Application Type | `Server` ou `Backend/Server-to-Server` (não é web nem mobile) |

## 4. Upload do certificado

Esta etapa é OBRIGATÓRIA em produção (Santander sandbox aceita sem cert em alguns fluxos, prod não).

- Sobe o MESMO `.pfx` que subiu em sandbox (Gaspar SC, CNPJ 35.588.873/0002-22)
- Se pedir a **chain pública separada** (`.cer`), usa o `soul_santander.cer` que geramos (você tem ele local)
- Se pedir a **thumbprint SHA-256** do cert: gera com  
  ```bash
  openssl pkcs12 -in "SOUL INDUSTRIA DE TECIDOS LTDA35588873000222 (1).pfx" -nokeys -legacy -passin pass:123456 | \
    openssl x509 -noout -fingerprint -sha256 | sed 's/://g' | cut -d= -f2
  ```

## 5. Ativar produto "Cobrança / Boletos"

Depois de criada a app:

- Na tela da app → aba **Products** ou **Subscribed Products**
- Botão **Add Product** ou **Subscribe**
- Procura por: `Cobrança`, `Emissão de Boletos`, `Collection Bill Management`, ou `Bank Slip Management`
- Clica **Subscribe**

Se der erro dizendo que o produto exige aprovação:
- Preenche o formulário de justificativa: `Cliente Soul Textil, convenio 0028697 ja ativo em producao, migrando emissao manual para API`
- Anota o ticket number
- Chama a Aline (analista Santander que já te atende) e pede pra ela aprovar/acompanhar

## 6. Capturar credenciais

Depois de app criada + produto subscrito, na tela da app aparecem:

- **Client ID** (também chamado `X-Application-Key` ou `Consumer Key`) → guarda
- **Client Secret** (também `Consumer Secret`) → clica em `Show` ou `Copy`, guarda

**Guarda no 1Password (ou similar), não em txt.** Isso é secret.

## 7. Testa o token de produção (curl)

Antes de mexer no n8n, valida via curl que a app prod funciona:

```bash
curl -sS -X POST "https://trust-open.api.santander.com.br/auth/oauth/v2/token" \
  --cert-type P12 \
  --cert "$HOME/Downloads/SOUL INDUSTRIA DE TECIDOS LTDA35588873000222 (1).pfx:123456" \
  -d "client_id=<CLIENT_ID_PROD>" \
  -d "client_secret=<CLIENT_SECRET_PROD>" \
  -d "grant_type=client_credentials"
```

Esperado: HTTP 200 + JSON com `access_token`.

Se der 401/403: a app não tá com o produto ativo ainda (volta ao passo 5) OU o cert não bate com o cadastrado (reupload).

## 8. Se travar em algum ponto específico

Me manda:
1. Qual passo (1 a 7)
2. Print da tela ou mensagem exata do erro
3. Se o erro veio do portal ou do curl

Vou ajudar a destravar.

---

## Quando isso terminar, ainda faltam:

1. **Bootstrap workspace prod** — rodar o curl §4 do `CHECKLIST_PRODUCAO.md` pra criar workspace de produção → guardar UUID
2. **Substituir 3 placeholders** no adapter (`Prod Token Santander` e `Fan Out Parcelas Santander`)
3. **Confirmar convênio 0028697 com Aline** — garantir que ele responde no CNPJ 0002-22 (senão outra parte precisa refazer)

Os 3 passos acima eu consigo automatizar (o #1 e #2), o #3 é ligação/email pra Aline.
