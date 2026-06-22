import streamlit as st
import utils
import auth



st.set_page_config(page_title="Logesti - Configurações Gerais", page_icon=":gear:", layout="wide")

auth.require_login()

FILE_ID = utils.FILE_ID
st.title("⚙️ Configurações Gerais")

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
        utils.save_km_rates(FILE_ID, {
            "valor_km_carro": valor_km_carro,
            "valor_km_moto": valor_km_moto
        })
        st.success("Valores por KM atualizados. Mudanças afetarão apenas contas novas.")
