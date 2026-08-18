# CLAUDE.md — Logesti Financeiro

Convenções do projeto pra qualquer agente (ou pessoa) trabalhando neste repo. Ler antes de implementar qualquer coisa.

## O que é

App interno de controle financeiro da Logesti Engenharia: clientes, orçamentos, contas a receber, contas a pagar e um consolidado (receita/despesa/lucro por cliente + despesas gerais da empresa). Uso restrito à equipe da empresa.

## Stack

- **Python 3.11** (`runtime.txt`) + **Streamlit 1.45** — multipage app: `Consolidado.py` é a home, cada `pages/NN_Nome.py` vira uma aba no menu lateral, ordenada pelo prefixo numérico
- **pandas** para toda manipulação de dados; **plotly** (`graph_objects`/`express`) para os gráficos do Consolidado
- **Sem banco de dados** — a "base" é uma planilha Google Sheets no Google Drive, acessada via `google-api-python-client` (Sheets API v4 pra ler/escrever cada aba; Drive API v3 só pra exportar a planilha inteira como Excel na leitura de Clientes/Orçamentos)
- Toda a lógica de acesso a dados (autenticação, load/save por aba, formatação BR) fica centralizada em `utils.py` — **não duplique isso dentro de uma página**, importe e reuse
- Sem framework de testes ou linter configurado no repo hoje (sem pytest/ruff/black/flake8) — ver `.claude/agents/test-engineer.md` pra como isso é tratado no fluxo

## Estrutura

- `Consolidado.py` — entry point / home (dashboard: totais por cliente, despesas da empresa, gráficos)
- `pages/01_Clientes.py`, `02_Orçamentos.py`, `03_Contas_A_Receber.py`, `04_Contas_A_Pagar.py`, `05_General_Settings.py` — um módulo por página
- `utils.py` — auth Google, load/save de cada aba (`load_incomes`, `load_outcomes`, `save_sheet`, ...), helpers de formatação (`format_brl`, `format_date_br`, `parse_currency`)
- `.streamlit/secrets.toml` (local, git-ignorado) / Secrets do Streamlit Cloud (produção) — credenciais Google e `FILE_ID` da planilha
- `credentials.json` / `token.json` (local, git-ignorado) — fluxo OAuth de desenvolvimento; não usados em produção

Ver `.claude/knowledge/` para detalhe de cada área antes de mexer nela.

## Índice de conhecimento (`.claude/knowledge/`)

- `data-model.md` — abas da planilha (schema de cada `*_DB`), como se relacionam
- `auth-and-sheets.md` — como a autenticação Google e o load/save de planilha funcionam, ordem de resolução de credenciais
- `ui-patterns.md` — padrão de página Streamlit usado no projeto (filtros, `st.tabs`, form, `@st.dialog` de confirmação, `session_state`)
- `business-rules.md` — glossário de domínio (Cliente, Orçamento, Receita, Despesa, parcelamento, recorrência, KM/Pro Labore)

Antes de mexer num desses temas, leia a nota correspondente — não repita de memória, confira contra o código.

## Convenções

- Nomes de coluna nas planilhas: sempre minúsculo (`nome`, `descricao`, `data_vencimento`...) — os loaders em `utils.py` já fazem `.str.lower()` nos headers lidos
- IDs: sempre `uuid4` em string, coluna `id`. Soft-delete via coluna `active` (bool) — **nunca remove linha de fato**, só marca `active = False`
- Datas: sempre convertidas pra `YYYY-MM-DD` antes de salvar (`pd.to_datetime(...).dt.strftime("%Y-%m-%d")`), exibidas em `DD/MM/YYYY` via `utils.format_date_br`
- Valores monetários: exibidos com `utils.format_brl` (`R$ 1.234,56`); ao ler da planilha, sempre parseados com `utils.parse_currency` (trata separador `.`/`,` no formato BR)
- Cache de sessão: dados carregados ficam em `st.session_state` (`clientes`, `orcamentos`) pra evitar round-trip repetido à API do Google a cada rerun. Após qualquer save bem-sucedido, atualize `st.session_state` manualmente com o novo dataframe
- Toda escrita bem-sucedida termina em `st.rerun()` (às vezes com `time.sleep()` curto antes, pra dar tempo da mensagem de sucesso aparecer)
- Ações destrutivas (desativar cliente, excluir conta/receita) sempre passam por um `@st.dialog` de confirmação — nunca excluir/desativar direto no clique do botão

## Tratamento de erros

- Toda chamada de escrita na planilha (`utils.save_sheet`, `utils.save_incomes`, etc.) fica dentro de `try/except`, com `st.error(f"Erro ao ...: {e}")` — nunca deixar exceção subir crua pra tela do Streamlit, nem engolir silenciosamente
- Falha ao carregar dados essenciais (estrutura de coluna inválida) usa `st.error(...)` + `st.stop()` (ver `utils.get_clientes_and_orcamentos`)

## Cuidados conhecidos

- **Autenticação por usuário foi tentada e revertida duas vezes** (commits `auth.py` / `Revert "auth.py"` — ver `git log --oneline`). Hoje o app não tem controle de acesso por e-mail dentro da aplicação; o controle de quem acessa é só via quem tem a URL/permissão no Streamlit Cloud. Se for reintroduzir isso, olhe o histórico revertido antes de reimplementar do zero — já não colou duas vezes.
- `utils.authenticate()` tenta múltiplas fontes de credencial em cascata (Streamlit secrets `google_service_account` → env var `GOOGLE_SERVICE_ACCOUNT_INFO` → arquivo de service account → Streamlit secrets `google_sheets_credentials` OAuth → `token.json` local → `credentials.json` + fluxo OAuth interativo). Não assuma qual está ativa sem checar o ambiente (local vs Streamlit Cloud) — ver `.claude/knowledge/auth-and-sheets.md`.

## Comandos

- `streamlit run Consolidado.py` — rodar localmente
- Sem lint/test configurado — se for adicionar uma ferramenta nova (pytest, ruff...), alinhe com o usuário antes; não introduza infra de dev sem pedir

## Deploy

Streamlit Community Cloud. Ver `DEPLOYMENT.md` para o passo a passo completo (credenciais como Secrets, `Consolidado.py` como main file).

## Fora de escopo deste projeto

- Sem rastreador de tarefas (Trello/Azure DevOps/Jira) — tarefas chegam como texto livre do usuário
- Sem backend separado — `utils.py` + Google Sheets é o backend inteiro; não há outro repositório irmão para depender

## Orchestrate

`/orchestrate <tarefa>` roda o fluxo completo (parser → análise/plano → aprovação → implementação → code review → validação → entrega) via os agentes em `.claude/agents/`. Ver `.claude/commands/orchestrate.md`.
