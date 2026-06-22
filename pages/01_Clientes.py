import streamlit as st
import pandas as pd
import uuid
import time

import utils
from googleapiclient.discovery import build

st.set_page_config(page_title="Logesti - Clientes", page_icon=":busts_in_silhouette:", layout="wide")
st.title("Logesti")

FILE_ID= utils.FILE_ID

clientes,orcamentos = utils.get_clientes_and_orcamentos()

st.subheader("Clientes")

# Show only active
active_clientes = clientes[clientes["active"] == True]

with st.expander("Tabela de clientes", False):
    st.dataframe(
        active_clientes.drop(columns=["id", "active"]),
        use_container_width=True
    )

tab1, tab2, tab3 = st.tabs(["Criar", "Editar", "Excluir"])

with tab1:
    with st.form("add_cliente"):
        nome = st.text_input("Nome")
        contato = st.text_input("Contato")
        email = st.text_input("E-mail")
        endereco = st.text_input("Endereço")
        km = st.number_input("KM", step=1)

        submitted = st.form_submit_button("Adicionar")

        if submitted:
            new_row = {
                "id": str(uuid.uuid4()),
                "nome": nome,
                "contato": contato,
                "e-mail": email,
                "endereco": endereco,
                "km": km,
                "active": True
            }

            clientes = pd.concat(
                [clientes, pd.DataFrame([new_row])], ignore_index=True)

            try:
                utils.save_sheet(FILE_ID,"CLIENTES_DB", clientes)
                st.session_state.clientes = clientes
                st.success("Cliente adicionado!")
                time.sleep(3)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao criar cliente: {e}")

id_to_label = {
    row["id"]: f'{row["nome"]} {"" if pd.isna(row["endereco"]) else f"({row['endereco']})"}'
    for _, row in clientes.iterrows()
}

with tab2:

    selected_id = st.selectbox(
        "Selecione cliente",
        options=active_clientes["id"],
        format_func=lambda x: id_to_label.get(x)
    )

    client = clientes.loc[clientes["id"] == selected_id]

    if client.empty:
        st.warning("Cliente não encontrado")
        st.stop()

    client = client.squeeze()

    with st.form("edit_cliente"):
        nome = st.text_input("Nome", client["nome"])
        contato = st.text_input("Contato", client["contato"])
        email = st.text_input("E-mail", client["e-mail"])
        endereco = st.text_input("Endereço", client["endereco"])
        km = st.number_input("KM", value=client["km"], step=1)


        submitted = st.form_submit_button("Salvar")

        if submitted:
            clientes.loc[clientes["id"] == selected_id, "nome"] = nome
            clientes.loc[clientes["id"] == selected_id, "contato"] = contato
            clientes.loc[clientes["id"] == selected_id, "e-mail"] = email
            clientes.loc[clientes["id"] == selected_id, "endereco"] = endereco
            clientes.loc[clientes["id"] == selected_id, "km"] = km
            try:
                utils.save_sheet(FILE_ID,"CLIENTES_DB", clientes)
                st.session_state.clientes = clientes
                st.success("Atualizado!")
                time.sleep(3)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar a atualização do cliente: {e}")
                clientes = st.session_state.clientes

@st.dialog(title="Confirmar desativação de clientes", width="small")
def confirm_deactivate_clients():
    pending = st.session_state.get("pending_deactivate_clients", [])
    if not pending:
        st.info("Nenhum cliente selecionado para desativar.")
        return

    st.write("Tem certeza que deseja desativar os clientes abaixo?")
    info_df = clientes[clientes["id"].isin(pending)][["nome", "contato", "endereco"]]
    st.dataframe(info_df)

    col1, col2 = st.columns(2, vertical_alignment="center")
    with col1:
        confirm = st.button("Sim, desativar", type="primary", use_container_width=True)
    with col2:
        cancel = st.button("Cancelar", use_container_width=True)

    if confirm:
        clientes.loc[clientes["id"].isin(pending), "active"] = False
        try:
            utils.save_sheet(FILE_ID, "CLIENTES_DB", clientes)
            st.session_state.clientes = clientes
            st.success("Clientes desativados")
        except Exception as e:
            st.error(f"Erro ao excluir cliente: {e}")
        time.sleep(0.5)
        del st.session_state["pending_deactivate_clients"]
        st.rerun()

    if cancel:
        st.info("Ação cancelada")
        del st.session_state["pending_deactivate_clients"]
        time.sleep(0.5)
        st.rerun()

with tab3:
    selected_ids = st.multiselect(
        "Selecione clientes para desativar",
        active_clientes["id"],
        format_func=lambda x: clientes.loc[clientes["id"]
                                        == x, "nome"].values[0]
    )

    if st.button("Desativar", key="deactivate_client"):
        st.session_state.pending_deactivate_clients = selected_ids
        confirm_deactivate_clients()
