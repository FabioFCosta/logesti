# Glossário de domínio

## Cliente

Empresa/pessoa atendida pela Logesti. Tem endereço e `km` (distância padrão até lá, usada em despesas de deslocamento). Vive em `CLIENTES_DB`.

## Orçamento

Um "cliente em potencial" — mesma estrutura de dados de Cliente (`ORCAMENTOS_DB`), mas ainda não fechado. Receitas/despesas podem apontar pra um orçamento (`quote_id`) antes dele virar cliente de fato. Quando o negócio fecha, o orçamento é "movido pra clientes" (`pages/02_Orçamentos.py`, aba "Enviar para clientes"): a linha é copiada pra `CLIENTES_DB` (mesmo `id`) e desativada em `ORCAMENTOS_DB`.

## Receita (Income) — Contas a Receber

Valor a receber de um cliente ou orçamento. Sempre tem `client_id` OU `quote_id` (não ambos). Tipos: Reembolso, Acompanhamento, Projeto, Administração, Orçamento, Perícia, Outros.

- **Parcelamento**: uma receita pode ser dividida em N parcelas no momento da criação (`grupo_id` compartilhado entre as parcelas, campo `parcela` tipo `"1/3"`). Cada parcela é uma linha independente em `INCOMES_DB` com seu próprio `id` e `saldo`, mas o progresso do grupo inteiro é exibido somado (`render_group_progress`).
- **Recebimento**: parcial ou total, registrado em `INCOMES_PAYMENTS_DB` (múltiplos pagamentos por receita são permitidos). Status calculado: `A Receber` (nada pago) → `Recebido Parcialmente` (`valor_pago > 0` e `saldo > 0`) → `Recebido` (`saldo == 0`).

## Despesa (Outcome) — Contas a Pagar

Valor a pagar. Duas categorias, diferenciadas só pela presença de `client_id`/`quote_id`:

- **Despesa de cliente**: `client_id` ou `quote_id` preenchido — custo atribuído a um cliente/orçamento específico, entra no cálculo de lucro por cliente (`Consolidado.py`).
- **Despesa da empresa**: nem `client_id` nem `quote_id` preenchido — custo administrativo geral (ex: Pro Labore, Contabilidade). Não entra no consolidado por cliente, aparece separado em "Despesas da empresa".

Tipos: Visita, Mão de obra, Pro Labore, Adquirir Ativo, Fornecedor, Impostos/Taxas, Utilização Carro, Utilização Moto, Gasolina, Reembolso, Alimentação, Contabilidade, Entrega Obras, Frete, Outros.

- **KM (Utilização Carro / Utilização Moto)**: `valor` é calculado (`km * km_rate`), não digitado. `km` sugere o valor cadastrado no cliente/orçamento (`clientes.km`), editável. `km_rate` é copiado de `GENERAL_SETTINGS_DB` (`valor_km_carro`/`valor_km_moto`) **no momento da criação** — mudar a taxa depois não recalcula despesas já lançadas.
- **Recorrência mensal**: `is_recurrent` + `recurrence_end_date` geram N linhas (uma por mês até a data de término), cada uma com `recurrence_parent_id` apontando pra linha original. Editar "aplicando às próximas ocorrências" (`update_future`) atualiza só as linhas futuras (`data_vencimento` posterior à editada) que compartilham o mesmo `recurrence_parent_id` ou são a própria raiz.
- **Pagamento**: parcial ou total, registrado em `PAYMENTS_OUT_DB`. Status calculado: `A Pagar` → `Vencido` (saldo > 0, nada pago, `data_vencimento` no passado) → `Pago Parcial` → `Pago`.

## Consolidado

`Consolidado.py` agrega, por cliente (juntando `CLIENTES_DB` e `ORCAMENTOS_DB` pelo campo `nome`): soma de receitas, soma de despesas de cliente, lucro (`receitas - despesas`) e "caixa" (mesmo valor que lucro, no momento). Separadamente, mostra o total de despesas da empresa (sem cliente atribuído) e o "Caixa Atual" (caixa dos clientes menos despesas da empresa). Pro Labore é destacado à parte dentro das despesas da empresa.

## Soft-delete (`active`)

Nada é excluído de fato — toda "exclusão"/"desativação" é `active = False`. Todas as queries de listagem/filtro devem considerar isso (`df[df["active"] == True]` ou variantes, atenção: em algumas planilhas o valor vem como string `"TRUE"`/`"FALSE"` em vez de bool — ver `pages/04_Contas_A_Pagar.py` que trata isso com `.str.upper() != "FALSE"`).
