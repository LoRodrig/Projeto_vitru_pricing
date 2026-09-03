# Monitor de preços EAD

Coleta periódica das mensalidades de cursos EAD de faculdades concorrentes, guardada no Supabase e visualizada num site simples (login + tabela) publicado no GitHub Pages.

## Como funciona

- **Fonte dos dados**: o agregador [ead.com.br](https://www.ead.com.br) (mesma plataforma de `querobolsa.com.br`) expõe, no HTML puro de cada faculdade, uma lista de ofertas de curso em microdata Schema.org (`Course` → `Offer` → `price`) — sem login, CEP ou JavaScript necessários. **Importante**: essa página mostra uma amostra de ofertas "com bolsa" — poucos cursos distintos por marca —, não o catálogo institucional completo. Valide se esse dado bate com o que você precisa antes de tratar como fonte definitiva.
- **Scraper** (`scraper/`): roda em Python, busca cada marca, extrai as ofertas e grava em `pricing_snapshots` no Supabase. Roda para todas as marcas com `"piloto": true` em `scraper/config/marcas.json` (hoje, as 132 marcas cadastradas). Cada snapshot registra também `valor_original` (quando a página mostra um preço "de/por"), `desconto` (coluna calculada: `valor_original > valor`), `modalidade` (hoje sempre `EAD`, único tipo raspado) e `origem` (hoje sempre `ead.com.br`, única fonte).
- **Automação**: `.github/workflows/scrape.yml` roda o scraper a cada 4 dias via GitHub Actions (grátis) e também pode ser disparado manualmente (aba Actions → "Scraping de preços EAD" → Run workflow).
- **Banco**: Supabase (Postgres). Ver `supabase/schema.sql` para o esquema completo, com Row Level Security ligado — só quem estiver autenticado lê os dados.
- **Site** (`site/`): página estática publicada no GitHub Pages via `.github/workflows/deploy-pages.yml`. Login único e compartilhado (ver seção de segurança abaixo).

## Segurança — por que isso protege o banco mesmo com o repositório visível a colaboradores

- A `service_role key` (que ignora toda proteção do banco) **nunca é commitada** — vive só como Secret do GitHub Actions, usada exclusivamente pelo workflow de scraping.
- O site usa a `anon key` + URL do projeto, que são **feitas para ser públicas** — quem as vê não consegue ler nenhuma linha das tabelas porque o RLS exige `authenticated`.
- Login é feito com **um único usuário do Supabase Auth** (e-mail + senha) que você cria manualmente no painel do Supabase e compartilha por fora do Git — a senha nunca entra em nenhum arquivo do repositório.
- Repositório **privado** impede que estranhos cheguem ao código pelo GitHub. A ressalva é a própria página publicada: no plano Free do GitHub, **GitHub Pages não tem controle de acesso** — o link `https://SEU_USUARIO.github.io/SEU_REPO/` fica no ar para quem tiver a URL, mas sem login válido a tela não carrega nenhum dado (é só o formulário).

## Passo a passo de configuração (uma vez)

1. **Criar o projeto no Supabase**: [supabase.com](https://supabase.com) → New project.
2. **Rodar o schema**: copie o conteúdo de `supabase/schema.sql` no SQL Editor do projeto e execute.
3. **Popular as tabelas de referência**: localmente, com Python e as libs de `scraper/requirements.txt` instaladas, crie um `.env` (copie de `.env.example`) com `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` (Project Settings → API), depois:
   ```
   cd scraper
   pip install -r requirements.txt
   python seed.py
   ```
4. **Criar o usuário de login compartilhado**: Supabase → Authentication → Users → Add user (e-mail + senha). Combine essa senha com quem for acessar o dashboard, fora do Git.
5. **Preencher `site/config.js`** com a `Project URL` e a `anon public key` (Project Settings → API) e commitar — são valores públicos por design.
6. **Criar o repositório no GitHub como privado** e subir o código (`git remote add origin ...`, `git push -u origin main`).
7. **Cadastrar os Secrets do repositório** (Settings → Secrets and variables → Actions): `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`.
8. **Habilitar o GitHub Pages** (Settings → Pages → Source: "GitHub Actions").
9. Disparar manualmente o workflow "Scraping de preços EAD" (aba Actions) para popular os primeiros dados, depois abrir o link do Pages e logar.

## Todas as 132 marcas ativas

Todas as marcas em `scraper/config/marcas.json` estão com `"piloto": true` — o scraper roda para as 132 a cada execução. Se quiser pausar alguma, mude sua flag para `false` e rode `python seed.py` de novo para sincronizar no banco.

Alguns slugs em `slug_ead` são um "chute" (nome normalizado); o site costuma redirecionar sozinho para o slug certo, mas se uma marca vier com "nenhuma oferta encontrada" no log do Actions, verifique manualmente a URL em `https://www.ead.com.br/faculdades/{slug}/cursos/a-distancia-ead` e corrija o `slug_ead` no JSON.

## Revisar classificação de cursos

`scraper/classify_curso.py` usa palavras-chave para mapear o nome do curso numa das 10 áreas do saber. Cursos que não batem com nenhuma palavra-chave ficam com área nula no banco — revise periodicamente com uma query tipo:
```sql
select distinct curso_nome from pricing_snapshots where grupo_curso_id is null;
```
e adicione as palavras-chave que faltarem em `classify_curso.py`.
