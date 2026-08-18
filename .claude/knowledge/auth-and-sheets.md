# Autenticação Google e acesso à planilha

Tudo isso vive em `utils.py`. Não reimplemente nada disso dentro de uma página — importe.

## Ordem de resolução de credenciais (`utils.authenticate`)

`authenticate()` tenta, nessa ordem, e usa a primeira que funcionar:

1. `st.secrets["google_service_account"]` — service account via Streamlit Secrets (produção recomendada)
2. `os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO")` — mesmo formato, via env var (JSON string)
3. `os.getenv("GOOGLE_APPLICATION_CREDENTIALS")` ou `SERVICE_ACCOUNT_FILE` — caminho pra arquivo de service account
4. `st.secrets["google_sheets_credentials"]` — credenciais OAuth de usuário via Streamlit Secrets (refresh automático se expirado)
5. `token.json` local — sessão OAuth já autorizada anteriormente
6. `credentials.json` local + `InstalledAppFlow.run_local_server` — abre navegador pra autorizar interativamente (só funciona local, nunca no Streamlit Cloud) e grava `token.json` pro próximo boot

Se nenhuma funcionar, `authenticate()` levanta `RuntimeError` explicando o que falta.

`SCOPES` inclui `spreadsheets` (leitura/escrita) e `drive.readonly` (só pra exportar planilha como Excel).

## Duas formas de ler dados — não são intercambiáveis

- **Sheets API `values().get(range=...)`** (`load_incomes`, `load_outcomes`, `load_outcome_payments`, `load_income_payments`, `load_km_rates`): lê os valores crus de um range (`"INCOMES_DB!A1:Z"`), primeira linha vira header. Preenche linhas curtas com `""` antes de montar o DataFrame (`normalized_rows`). Usada pra tudo que muda com frequência.
- **Drive API `export_media` + `pd.read_excel`** (`load_db_sheets`, usado só por `get_clientes_and_orcamentos`): baixa a planilha inteira exportada como `.xlsx` e lê com pandas. Mais pesado — por isso Clientes/Orçamentos ficam em cache de `st.session_state` (`get_clientes_and_orcamentos` só recarrega se `"clientes" not in st.session_state`).

Se for adicionar um loader novo, siga o padrão Sheets API `values().get` (mais leve, mais consistente com o resto) a menos que haja um motivo específico pra usar export do Drive.

## Salvando dados

- `utils.save_sheet(file_id, sheet_name, df)` — grava a aba inteira (sobrescreve `A1` em diante) via `spreadsheets().values().batchUpdate`. `fillna("")` antes de salvar; converte coluna `active` pra bool se presente. É o caminho padrão pra qualquer save.
- `utils.save_incomes(file_id, df)` — variante específica só pra `INCOMES_DB`, usada em alguns fluxos de `pages/03_Contas_A_Receber.py` (histórico legado; `save_sheet` faria a mesma coisa apontando pra `"INCOMES_DB"`).
- `utils.ensure_sheet_exists(file_id, sheet_name)` — cria a aba se não existir (usado antes de `save_km_rates`, por exemplo). Chame isso antes de salvar numa aba nova que pode não existir ainda na planilha.

**Sempre convertar colunas de data pra string `YYYY-MM-DD` antes de chamar `save_sheet`** (`df["data"] = pd.to_datetime(df["data"]).dt.strftime("%Y-%m-%d")`) — salvar um objeto `Timestamp` direto quebra a leitura seguinte. Isso é repetido manualmente em cada página antes de cada save; se for extrair um helper genérico, siga o padrão `normalize_dates_for_sheets` já usado em `pages/04_Contas_A_Pagar.py`.

## `FILE_ID`

Resolvido uma vez no import de `utils.py`: `os.getenv("FILE_ID") or st.secrets.get("FILE_ID")`. Toda página importa `utils` e usa `utils.FILE_ID` — não leia a env var de novo dentro de uma página.
