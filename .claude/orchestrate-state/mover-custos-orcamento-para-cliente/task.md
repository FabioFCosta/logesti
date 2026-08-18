# Tarefa: mover-custos-orcamento-para-cliente

**Resumo:** Ao promover orçamento pra cliente (`pages/02_Orçamentos.py`, tab "Enviar para clientes"), receitas/despesas antigas continuam apontando pro `quote_id` do orçamento, não pro `client_id` novo. Consolidado (`Consolidado.py`) agrupa por `nome` resolvido via `client_id`/`quote_id` — se o nome do orçamento difere do nome do cliente promovido (ex: orçamento "Marlã (cliente Bruno)", cliente promovido "Marlã"), a mesma entidade real vira duas linhas separadas no consolidado, receita/despesa fragmentada em vez de somada.

**Critérios de aceite:** N/A (não formalizados)

**Contexto relevante:**
- Reprodução relatada pelo usuário: "Marlã" (cliente) aparece separado de "Marlã (cliente Bruno)" (orçamento) no consolidado — mesma obra/cliente, dois totais.
- Promoção hoje só copia linha de `ORCAMENTOS_DB` → `CLIENTES_DB` e desativa em `ORCAMENTOS_DB`; não toca `INCOMES_DB`/`OUTCOMES_DB`.
- Usuário espera que ao promover, custo "mova junto" — deixe de contar separado e passe a somar com o cliente novo.
- Nem todo orçamento vira cliente — migração de vínculo só no momento da promoção, não mudança geral em como `quote_id` funciona (despesas de orçamento que nunca vira cliente continuam como hoje).
- Ambiguidade pro plano: "mover os custos" pode ser (a) re-apontar `quote_id → client_id` nas linhas existentes de `INCOMES_DB`/`OUTCOMES_DB` no momento da promoção, ou (b) manter `quote_id` mas fazer o Consolidado somar cliente+orçamento promovido junto (a promoção preserva o `id` original — ver `.claude/knowledge/data-model.md`, seção "Relação entre abas" — então (b) pode ser mais simples, sem reescrever histórico).
