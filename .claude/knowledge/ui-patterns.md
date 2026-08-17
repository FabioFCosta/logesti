# Padrão de página Streamlit

Todas as páginas em `pages/` seguem a mesma receita. Ao criar/alterar uma página, siga esse padrão em vez de inventar um novo.

## Esqueleto de página

```python
import streamlit as st
import utils

FILE_ID = utils.FILE_ID

st.set_page_config(page_title="Logesti - <Nome>", page_icon=":emoji:", layout="wide")
st.title("<Título>")

# 1. Carregar dados (via utils, nunca chamada direta à API aqui)
dados = utils.load_x(FILE_ID)

# 2. Filtros (quando a página lista muitos registros)
# 3. Métricas (st.metric / cards em HTML customizado, ver Consolidado.py)
# 4. Tabela em st.expander (colapsada por padrão, exceto onde já está expanded=True)
# 5. st.tabs pras ações (Criar / Editar / Registrar pagamento / Excluir)
```

## Filtros

Ano/Mês/Status/Cliente via `st.selectbox` em colunas (`st.columns(3)` ou `st.columns(4)`), sempre com opção `"Todos"` no topo da lista. Ver `pages/03_Contas_A_Receber.py` e `pages/04_Contas_A_Pagar.py` pro padrão exato de `years`/`months`/`month_names`.

## Seleção de registro (padrão `id_to_label`)

Pra selects que representam um registro (cliente, orçamento, receita, conta), monte um dict `id → label legível` e use `format_func`:

```python
id_to_label = {
    row["id"]: f'{utils.format_date_br(row["data"])} | {row["descricao"]} ({utils.format_brl(row["saldo"])})'
    for _, row in df.iterrows()
}
selected_id = st.selectbox("Receita", options=df["id"], format_func=lambda x: id_to_label.get(x))
```

Nunca use o índice do DataFrame como chave de seleção — sempre o `id` (uuid).

## Formulário: inputs fora vs dentro do `st.form`

Regra do projeto: **inputs que precisam reagir uns aos outros em tempo real (recalcular um valor, mostrar/esconder campo condicional) ficam FORA do `st.form`**; o `st.form` só envolve o botão de submit. Exemplo (`pages/04_Contas_A_Pagar.py`, criação de conta tipo KM): tipo/km/checkbox ficam soltos na página pra que o valor calculado (`km * km_rate`) atualize a cada rerun; só `st.form_submit_button` fica dentro do `with st.form(...)`.

Quando não há necessidade de reatividade (formulário simples, tipo cadastro de cliente), o formulário inteiro fica dentro do `st.form` normalmente (`pages/01_Clientes.py`).

## Confirmação de ação destrutiva

Sempre via `@st.dialog`, nunca ação direta no clique:

```python
@st.dialog(title="Confirmar exclusão", width="small")
def confirm_delete():
    st.write("Tem certeza...?")
    col1, col2 = st.columns(2, vertical_alignment="center")
    with col1:
        confirm = st.button("Sim, excluir", type="primary", use_container_width=True)
    with col2:
        cancel = st.button("Cancelar", use_container_width=True)
    if confirm:
        # aplica active = False, salva, st.success, time.sleep(0.5), st.rerun()
        ...
    if cancel:
        st.info("Ação cancelada")
        time.sleep(0.5)
        st.rerun()
```

Para exclusão em lote (ex: desativar múltiplos clientes), guarde os ids pendentes em `st.session_state.pending_deactivate_x` antes de abrir o diálogo, e apague essa chave do `session_state` depois de confirmar/cancelar.

## `session_state` pra widgets com preenchimento auxiliar

Padrão usado no preenchimento de parcelas personalizadas (`pages/03_Contas_A_Receber.py`, "Preencher parcelas restantes automaticamente"): grava um flag (`auto_fill_requested`) no `session_state`, processa e atualiza os valores **antes** de renderizar os widgets, depois `st.rerun()`. Nunca tente mudar o valor de um widget já renderizado no mesmo ciclo — sempre recalcule antes do `st.number_input`/`st.selectbox` correspondente ser desenhado.

## Após qualquer save

```python
utils.save_sheet(FILE_ID, "ALGUMA_DB", df)
st.session_state.algo = df  # atualiza o cache, se essa aba for cacheada
st.success("Mensagem")
time.sleep(3)  # dá tempo do usuário ler a mensagem (0.5s em diálogos, ~3s em forms)
st.rerun()
```

Sempre dentro de `try/except`, com `st.error(f"Erro ao ...: {e}")` no except (ver seção "Tratamento de erros" do `CLAUDE.md`).
