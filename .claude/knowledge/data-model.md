# Data model — abas da planilha Google Sheets

A "base de dados" inteira é uma única planilha Google Sheets (`FILE_ID` em `.env`/secrets). Cada aba é carregada/salva via `utils.py` como um DataFrame pandas. Não existe schema/migração formal — o schema é o conjunto de colunas que os loaders esperam encontrar (ver `required_cols` em `utils.get_clientes_and_orcamentos`, por exemplo).

## CLIENTES_DB

Carregada via `utils.load_db_sheets` (export do Drive como Excel, `pd.read_excel`).

| coluna | tipo | notas |
|---|---|---|
| `id` | uuid str | gerado por `utils.normalize_df` se vazio |
| `nome` | str | |
| `contato` | str | telefone/contato |
| `e-mail` | str | atenção: hífen no nome da coluna, não `email` |
| `endereco` | str | usado pra montar o label `nome (endereco)` nos selects |
| `km` | float | distância padrão até o cliente — usado como default em despesas "Utilização Carro/Moto" |
| `active` | bool | soft-delete |

## ORCAMENTOS_DB

Mesmo shape de `CLIENTES_DB` (mesmas colunas, mesma validação de `required_cols`). Representa um cliente ainda não fechado — um orçamento pode "virar" cliente (`pages/02_Orçamentos.py`, aba "Enviar para clientes": copia a linha pra `CLIENTES_DB` com `active=True` e desativa em `ORCAMENTOS_DB`).

## INCOMES_DB (Contas a Receber)

Carregada via `utils.load_incomes` (Sheets API `values.get`, não Excel).

| coluna | tipo | notas |
|---|---|---|
| `id` | uuid str | |
| `grupo_id` | uuid str, opcional | presente só quando a receita foi criada parcelada — agrupa as parcelas |
| `descricao` | str | |
| `valor` | float | parseado com `utils.parse_currency` |
| `parcela` | str | ex: `"1/3"`, só em receitas parceladas |
| `client_id` | uuid str, opcional | FK pra `CLIENTES_DB.id` |
| `quote_id` | uuid str, opcional | FK pra `ORCAMENTOS_DB.id` — mutuamente exclusivo com `client_id` na prática |
| `data` | date | parseada com `dayfirst=True`; linhas sem data válida são descartadas no load |
| `tipo` | str | um de: Reembolso, Acompanhamento, Projeto, Administração, Orçamento, Perícia, Outros |
| `active` | bool | soft-delete |

Status é **calculado em runtime**, não armazenado (`build_financial_view` em `pages/03_Contas_A_Receber.py`): `Recebido` / `Recebido Parcialmente` / `A Receber`, a partir do saldo (`valor - valor_pago`, `valor_pago` vindo de `INCOMES_PAYMENTS_DB`).

## INCOMES_PAYMENTS_DB

| coluna | tipo | notas |
|---|---|---|
| `id` | uuid str | |
| `income_id` | uuid str | FK pra `INCOMES_DB.id` |
| `data_pagamento` | date | |
| `valor_pago` | float | |

Uma receita pode ter múltiplos pagamentos (recebimento parcial ao longo do tempo) — sempre agrupados por `income_id` (`.groupby("income_id")["valor_pago"].sum()`) antes de calcular saldo.

## OUTCOMES_DB (Contas a Pagar)

Carregada via `utils.load_outcomes` (Sheets API `values.get`).

| coluna | tipo | notas |
|---|---|---|
| `id` | uuid str | |
| `descricao` | str | |
| `valor` | float | calculado como `km * km_rate` quando `tipo` é KM |
| `data_vencimento` | date | parseada com `dayfirst=True`; linhas sem data válida são descartadas no load |
| `tipo` | str | Visita, Mão de obra, Pro Labore, Adquirir Ativo, Fornecedor, Impostos/Taxas, Utilização Carro, Utilização Moto, Gasolina, Reembolso, Alimentação, Contabilidade, Entrega Obras, Frete, Outros |
| `quem_pagar` | str | |
| `client_id` | uuid str, opcional | FK pra `CLIENTES_DB.id` — despesa **do cliente** |
| `quote_id` | uuid str, opcional | FK pra `ORCAMENTOS_DB.id` |
| `km` | float, opcional | só em tipo "Utilização Carro"/"Utilização Moto" |
| `km_rate` | float, opcional | copiado de `GENERAL_SETTINGS_DB` no momento da criação — não recalcula retroativamente se a taxa mudar depois |
| `is_recurrent` | bool | despesa recorrente mensal |
| `recurrence_end_date` | date, opcional | só se `is_recurrent` |
| `recurrence_parent_id` | uuid str, opcional | aponta pra linha "raiz" quando a linha foi gerada por recorrência |
| `active` | bool | soft-delete |

**Despesa sem `client_id` nem `quote_id` preenchido = despesa da empresa** (ex: Pro Labore, Contabilidade), não de um cliente específico — é assim que `Consolidado.py` separa "despesas de cliente" de "despesas da empresa" (`cliente_nome.apply(lambda x: pd.isna(x) or str(x).strip() == "")`).

Status calculado em runtime (`build_financial_view` em `pages/04_Contas_A_Pagar.py`): `Pago` / `Pago Parcial` / `Vencido` (saldo > 0, nada pago, `data_vencimento` no passado) / `A Pagar`.

## PAYMENTS_OUT_DB

Mesmo shape de `INCOMES_PAYMENTS_DB`, mas com `outcome_id` no lugar de `income_id`.

## GENERAL_SETTINGS_DB

Formato chave/valor, não tabular:

| coluna | notas |
|---|---|
| `key` | nome da tarifa (`valor_km_carro`, `valor_km_moto`) ou nome da opção de tipo |
| `value` | float, parseado com vírgula BR — só usado por `type == "km"`, vazio pras opções de tipo |
| `type` | `"km"` (tarifas por KM, gerenciadas só pela aba "Valores por KM"), `"income_options"` (opções do dropdown de tipo de receita em `pages/03`) ou `"outcomes_options"` (opções do dropdown de tipo de despesa em `pages/04`, exceto os reservados "Utilização Carro"/"Utilização Moto" que ficam hardcoded fora dessa aba) |
| `active` | bool, soft-delete das opções de tipo. Ausente em linhas antigas de `type == "km"` — tratado como `True` no load |

Editado em `pages/05_General_Settings.py` (uma aba por categoria: KM / Tipos de Receita / Tipos de Despesa). Lido por `utils.load_km_rates` (só linhas `type == "km"`) e `utils.load_type_options` (só linhas `type == categoria`, com seed automático na primeira execução se a categoria ainda não tiver nenhuma linha). Toda escrita (`save_km_rates`, `save_type_option`, `set_type_option_active`) faz load-modify-save da aba **inteira**, pra nunca sobrescrever as linhas das outras categorias. Mudar a taxa de KM **não** recalcula despesas já lançadas (elas guardam `km_rate` próprio no momento da criação).

## Relação entre abas

```
CLIENTES_DB ──┐
              ├─(client_id / quote_id, mutuamente exclusivos)─→ INCOMES_DB ──(income_id)──→ INCOMES_PAYMENTS_DB
ORCAMENTOS_DB ┘                                                  OUTCOMES_DB ──(outcome_id)─→ PAYMENTS_OUT_DB
```

Um orçamento "promovido" a cliente (`pages/02_Orçamentos.py`) preserva o `id` original — receitas/despesas que apontavam pro `quote_id` continuam válidas, mas o `client_id` correspondente não é retroativamente preenchido.
