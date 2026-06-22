import streamlit as st
import pandas as pd
import uuid
import time
import utils
from googleapiclient.discovery import build
import auth



st.set_page_config(page_title="Logesti - Orçamentos",
                   page_icon=":clipboard:", layout="wide")

auth.require_login()
st.title("Logesti")

FILE_ID = utils.FILE_ID

clientes, orcamentos = utils.get_clientes_and_orcamentos()

st.subheader("Orçamentos")

# Show only active
active_orcamentos = orcamentos[orcamentos["active"] == True]

with st.expander("Tabela de orçamentos", False):
    st.dataframe(
        active_orcamentos.drop(columns=["id", "active"]),
        use_container_width=True
    )

tab1, tab2, tab3, tab4 = st.tabs(
    ["Criar novo", "Editar", "Enviar para clientes", "Excluir"])

with tab1:
    with st.form("add_orcamento"):
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

            orcamentos = pd.concat(
                [orcamentos, pd.DataFrame([new_row])], ignore_index=True)

            try:
                utils.save_sheet(FILE_ID, "ORCAMENTOS_DB", orcamentos)
                st.session_state.orcamentos = orcamentos
                st.success("Orçamento adicionado!")
                time.sleep(3)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao criar orçamento: {e}")

with tab2:
    id_to_label = {
        row["id"]: (
            row["nome"]
            if pd.isna(row["endereco"])
            else f'{row["nome"]} ({row["endereco"]})'
        )
        for _, row in orcamentos.iterrows()
    }

    selected_id = st.selectbox(
        "Selecione orçamento",
        options=active_orcamentos["id"],
        format_func=lambda x: id_to_label.get(x)
    )

    client = orcamentos.loc[orcamentos["id"] == selected_id]

    if client.empty:
        st.warning("Orçamento não encontrado")
        st.stop()

    client = client.squeeze()

    with st.form("edit_orcamento"):
        nome = st.text_input("Nome", client["nome"])
        contato = st.text_input("Contato", client["contato"])
        email = st.text_input("E-mail", client["e-mail"])
        endereco = st.text_input("Endereço", client["endereco"])
        km = st.number_input("KM", value=client["km"], step=1)

        submitted = st.form_submit_button("Salvar")

        if submitted:
            orcamentos.loc[orcamentos["id"] == selected_id, "nome"] = nome
            orcamentos.loc[orcamentos["id"] ==
                           selected_id, "contato"] = contato
            orcamentos.loc[orcamentos["id"] == selected_id, "e-mail"] = email
            orcamentos.loc[orcamentos["id"] ==
                           selected_id, "endereco"] = endereco
            orcamentos.loc[orcamentos["id"] == selected_id, "km"] = km

            try:
                utils.save_sheet(FILE_ID, "ORCAMENTOS_DB", orcamentos)
                st.session_state.orcamentos = orcamentos
                st.success("Atualizado!")
                time.sleep(3)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar a atualização do orçamento: {e}")
                orcamentos = st.session_state.orcamentos

with tab3:
    selected_ids = st.multiselect(
        "Selecione orçamento para mover para a aba de clientes:",
        active_orcamentos["id"],
        format_func=lambda x: orcamentos.loc[orcamentos["id"]
                                             == x, "nome"].values[0],
        key="move_client_widget"
    )
    if st.button("Mover para clientes", key="move_orcamento"):
        clients_to_move = orcamentos.loc[orcamentos["id"].isin(
            selected_ids)].copy()
        clients_to_move["active"] = True
        new_clientes = pd.concat(
            [clientes, clients_to_move], ignore_index=True)

        try:
            utils.save_sheet(FILE_ID, "CLIENTES_DB", new_clientes)
            orcamentos.loc[orcamentos["id"].isin(
                selected_ids), "active"] = False
            utils.save_sheet(FILE_ID, "ORCAMENTOS_DB", orcamentos)

            st.session_state.clientes = new_clientes
            st.session_state.orcamentos = orcamentos
            st.success("Orçamentos movidos para clientes")

        except Exception as e:
            st.error(f"Erro ao mover orçamento: {e}")
            orcamentos = st.session_state.orcamentos

        time.sleep(3)
        st.rerun()


@st.dialog(title="Confirmar desativação de orçamentos", width="small")
def confirm_deactivate_orcamentos():
    pending = st.session_state.get("pending_deactivate_orcamentos", [])
    if not pending:
        st.info("Nenhum orçamento selecionado para desativar.")
        return

    st.write("Tem certeza que deseja desativar os orçamentos abaixo?")
    info_df = orcamentos[orcamentos["id"].isin(
        pending)][["nome", "contato", "endereco"]]
    st.dataframe(info_df)

    col1, col2 = st.columns(2, vertical_alignment="center")
    with col1:
        confirm = st.button("Sim, desativar", type="primary",
                            use_container_width=True)
    with col2:
        cancel = st.button("Cancelar", use_container_width=True)

    if confirm:
        orcamentos.loc[orcamentos["id"].isin(pending), "active"] = False
        try:
            utils.save_sheet(FILE_ID, "ORCAMENTOS_DB", orcamentos)
            st.session_state.orcamentos = orcamentos
            st.success("Orçamentos desativados")
        except Exception as e:
            st.error(f"Erro ao mover orçamento: {e}")
        time.sleep(0.5)
        del st.session_state["pending_deactivate_orcamentos"]
        st.rerun()

    if cancel:
        st.info("Ação cancelada")
        del st.session_state["pending_deactivate_orcamentos"]
        time.sleep(0.5)
        st.rerun()


with tab4:
    selected_ids = st.multiselect(
        "Selecione orçamentos para excluir",
        active_orcamentos["id"],
        format_func=lambda x: orcamentos.loc[orcamentos["id"]
                                             == x, "nome"].values[0]
    )

    if st.button("Desativar", key="deactivate_orcamento"):
        st.session_state.pending_deactivate_orcamentos = selected_ids
        confirm_deactivate_orcamentos()
