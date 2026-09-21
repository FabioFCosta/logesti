# Tarefa: settings-opcoes-selects-tipo

**Resumo:** Opções de "Tipo" nos selects de Contas a Pagar (`outcomes_types`, `pages/04_Contas_A_Pagar.py`) e Contas a Receber (lista inline, `pages/03_Contas_A_Receber.py`) são hardcoded no Python. Usuário quer editar/adicionar essas opções pela tela de Configurações Gerais (`pages/05_General_Settings.py`), sem mexer em código.

**Critérios de aceite:** N/A (não formalizados)

**Contexto relevante:**
- Tipos hardcoded hoje:
  - Contas a Pagar: Visita, Mão de obra, Pro Labore, Adquirir Ativo, Fornecedor, Impostos/Taxas, Utilização Carro, Utilização Moto, Gasolina, Reembolso, Alimentação, Contabilidade, Entrega Obras, Frete, Outros.
  - Contas a Receber: Reembolso, Acompanhamento, Projeto, Administração, Orçamento, Perícia, Outros.
- `GENERAL_SETTINGS_DB` hoje só guarda `valor_km_carro`/`valor_km_moto`, formato chave/valor (`.claude/knowledge/data-model.md`) — decidir no plano: reusar esse formato (chave `tipos_despesa`/`tipos_receita` serializada) ou aba nova (ex: `TIPOS_DB` com coluna categoria).
- "Utilização Carro"/"Utilização Moto" têm comportamento especial hoje (cálculo automático de valor via KM, ver `.claude/knowledge/business-rules.md`) — se virar editável via Settings, decidir se esse comportamento fica fixo por nome de tipo (risco: usuário renomeia/apaga o tipo e quebra o cálculo) ou vira flag configurável.
- Escopo a confirmar com usuário: só Contas a Pagar, só Contas a Receber, ou os dois.
