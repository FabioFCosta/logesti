import streamlit as st
import time

import utils

FILE_ID = utils.FILE_ID

st.set_page_config(page_title="Logesti - Configurações Gerais", page_icon=":gear:", layout="wide")
st.title("⚙️ Configurações Gerais")


def render_type_manager(file_id, category, label, reserved=None):
    reserved = reserved or []
    options = utils.load_type_options(file_id, category)

    st.subheader(f"Opções ativas — {label}")
    if options:
        st.dataframe({label: options}, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma opção cadastrada ainda.")

    with st.form(f"add_{category}"):
        nome = st.text_input("Nova opção", key=f"input_{category}")
        submitted = st.form_submit_button("Adicionar")

        if submitted:
            nome = nome.strip()
            if not nome:
                st.error("Informe um nome para a opção.")
            elif nome in options:
                st.error("Essa opção já existe.")
            elif nome in reserved:
                st.error("Esse nome é reservado pelo sistema e não pode ser cadastrado aqui.")
            else:
                try:
                    utils.save_type_option(file_id, category, nome)
                    st.success("Opção adicionada!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao adicionar opção: {e}")

    if options:
        st.subheader("Desativar opção")
        col1, col2 = st.columns([3, 1])
        with col1:
            selected = st.selectbox(
                "Selecione a opção",
                options=options,
                key=f"select_deactivate_{category}"
            )
        with col2:
            st.write("")
            st.write("")
            if st.button("Desativar", key=f"deactivate_btn_{category}"):
                st.session_state[f"pending_deactivate_{category}"] = selected
                confirm_deactivate_type_option(file_id, category, label)


@st.dialog(title="Confirmar desativação", width="small")
def confirm_deactivate_type_option(file_id, category, label):
    pending = st.session_state.get(f"pending_deactivate_{category}")
    if not pending:
        st.info("Nenhuma opção selecionada para desativar.")
        return

    st.write(f"Tem certeza que deseja desativar a opção **{pending}** de {label}?")

    col1, col2 = st.columns(2, vertical_alignment="center")
    with col1:
        confirm = st.button("Sim, desativar", type="primary", use_container_width=True)
    with col2:
        cancel = st.button("Cancelar", use_container_width=True)

    if confirm:
        try:
            utils.set_type_option_active(file_id, category, pending, False)
            st.success("Opção desativada.")
        except Exception as e:
            st.error(f"Erro ao desativar opção: {e}")
        time.sleep(0.5)
        del st.session_state[f"pending_deactivate_{category}"]
        st.rerun()

    if cancel:
        st.info("Ação cancelada")
        del st.session_state[f"pending_deactivate_{category}"]
        time.sleep(0.5)
        st.rerun()


tab_km, tab_income, tab_outcome = st.tabs(
    ["Valores por KM", "Tipos de Receita", "Tipos de Despesa"])

with tab_km:
    rates = utils.load_km_rates(FILE_ID)

    with st.form("general_settings"):
        valor_km_carro = st.number_input(
            "Valor por KM Carro",
            min_value=0.0,
            value=float(rates.get("valor_km_carro", 0.0)),
            step=0.1,
            format="%.2f"
        )
        valor_km_moto = st.number_input(
            "Valor por KM Moto",
            min_value=0.0,
            value=float(rates.get("valor_km_moto", 0.0)),
            step=0.1,
            format="%.2f"
        )

        submitted = st.form_submit_button("Salvar")

        if submitted:
            try:
                utils.save_km_rates(FILE_ID, {
                    "valor_km_carro": valor_km_carro,
                    "valor_km_moto": valor_km_moto
                })
                st.success("Valores por KM atualizados. Mudanças afetarão apenas contas novas.")
            except Exception as e:
                st.error(f"Erro ao salvar valores por KM: {e}")

with tab_income:
    render_type_manager(FILE_ID, "income_options", "Tipos de Receita")

with tab_outcome:
    render_type_manager(
        FILE_ID, "outcomes_options", "Tipos de Despesa",
        reserved=["Utilização Carro", "Utilização Moto"]
    )
