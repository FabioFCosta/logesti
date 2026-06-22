import streamlit as st
import utils
import pandas as pd
import uuid
import time
from dateutil.relativedelta import relativedelta

FILE_ID = utils.FILE_ID

st.set_page_config(page_title="Logesti - Contas a Pagar",
                   page_icon=":money_with_wings:", layout="wide")
st.title("💸 Contas a Pagar")

def ensure_outcome_ids(file_id, df):
    df = df.copy()

    if "id" not in df.columns:
        df["id"] = None

    mask = df["id"].isna() | (df["id"] == "")
    if mask.any():
        df.loc[mask, "id"] = [str(uuid.uuid4()) for _ in range(mask.sum())]

        df_to_save = df.copy()
        df_to_save["data_vencimento"] = df_to_save["data_vencimento"].dt.strftime(
            "%Y-%m-%d")

        utils.save_sheet(file_id, "OUTCOMES_DB", df_to_save)

    return df


def build_financial_view(outcomes, payments):
    payments_grouped = (
        payments.groupby("outcome_id")["valor_pago"]
        .sum()
        .reset_index()
    )

    df = outcomes.merge(
        payments_grouped,
        left_on="id",
        right_on="outcome_id",
        how="left"
    )

    df = df[df["active"] != False]

    df["valor_pago"] = df["valor_pago"].fillna(0)

    df["saldo"] = df["valor"] - df["valor_pago"]

    today = pd.Timestamp.today()

    df["status"] = "A Pagar"

    df.loc[df["saldo"] == 0, "status"] = "Pago"

    df.loc[(df["saldo"] > 0) & (df["valor_pago"] > 0),
           "status"] = "Pago Parcial"

    df.loc[
        (df["saldo"] > 0) &
        (df["valor_pago"] == 0) &
        (df["data_vencimento"] < today),
        "status"
    ] = "Vencido"

    return df


def add_payment(file_id, payments_df, outcome_id, valor, data_pagamento):
    new_payment = {
        "id": str(uuid.uuid4()),
        "outcome_id": outcome_id,
        "data_pagamento": data_pagamento,
        "valor_pago": valor
    }

    new_df = pd.concat(
        [payments_df, pd.DataFrame([new_payment])],
        ignore_index=True
    )

    new_df["data_pagamento"] = pd.to_datetime(
        new_df["data_pagamento"]).dt.strftime("%Y-%m-%d")

    utils.save_sheet(file_id, "PAYMENTS_OUT_DB", new_df)


def create_recurrent_outcomes(base_outcome, start_date, end_date):
    """
    Create multiple outcome records for each month from start_date to end_date.
    Returns a list of outcome dictionaries.
    """
    outcomes_list = [base_outcome.copy()]

    current_date = pd.to_datetime(start_date) + relativedelta(months=1)
    end_date_pd = pd.to_datetime(end_date)

    while current_date <= end_date_pd:
        new_outcome = base_outcome.copy()
        new_outcome["id"] = str(uuid.uuid4())
        new_outcome["data_vencimento"] = current_date.strftime("%Y-%m-%d")
        new_outcome["recurrence_parent_id"] = base_outcome["id"]
        outcomes_list.append(new_outcome)
        current_date += relativedelta(months=1)

    return outcomes_list


def to_iso_date(value):
    if not value:
        return ""
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def normalize_dates_for_sheets(df):
    df = df.copy()

    for col in df.columns:
        if "data" in col:
            df[col] = df[col].apply(
                lambda x: pd.to_datetime(x).strftime("%Y-%m-%d")
                if pd.notnull(x) and x != ""
                else ""
            )

    return df


outcomes = utils.load_outcomes(FILE_ID)
payments = utils.load_outcome_payments(FILE_ID)

outcomes = ensure_outcome_ids(FILE_ID, outcomes)

outcomes_types = [
    "Visita", "Mão de obra", "Pro Labore",
    "Adquirir Ativo", "Fornecedor", "Impostos/Taxas",
    "Utilização Carro", "Utilização Moto", "Gasolina", "Reembolso", "Alimentação", "Contabilidade", "Entrega Obras","Frete", "Outros"
]

df = build_financial_view(outcomes, payments)

clientes, orcamentos = utils.get_clientes_and_orcamentos()

clientes_map = {
    row["id"]: f'{row["nome"]} ({row["endereco"]})'
    for _, row in clientes.iterrows()
    if row["active"] == True
}

orcamentos_map = {
    row["id"]: f'{row["nome"]} ({row["endereco"]})'
    for _, row in orcamentos.iterrows()
    if row["active"] == True
}

km_rates = utils.load_km_rates(FILE_ID)
valor_km_carro = km_rates.get("valor_km_carro", 0.0)
valor_km_moto = km_rates.get("valor_km_moto", 0.0)

st.subheader("Filtros")

col1, col2 = st.columns(2)

with col1:
    ano = st.selectbox("Ano", ["Todos"] +
                       sorted(df["data_vencimento"].dt.year.unique()))

with col2:
    mes = st.selectbox("Mês", ["Todos"] + list(range(1, 13)))

active_outcomes = df[df["active"].str.upper() != "FALSE"]

if ano != "Todos" and mes != "Todos":
    filtered = df[
        (active_outcomes["data_vencimento"].dt.year == ano) &
        (active_outcomes["data_vencimento"].dt.month == mes)
    ]
elif ano != "Todos":
    filtered = active_outcomes[active_outcomes["data_vencimento"].dt.year == ano]
elif mes != "Todos":
    filtered = active_outcomes[active_outcomes["data_vencimento"].dt.month == mes]
else:
    filtered = active_outcomes

total = filtered["valor"].sum()
pago = filtered["valor_pago"].sum()
saldo = filtered["saldo"].sum()

k1, k2, k3 = st.columns(3)

k1.metric("Total", utils.format_brl(total))
k2.metric("Pago", utils.format_brl(pago))
k3.metric("A Pagar", utils.format_brl(saldo))

with st.expander("Tabela de contas", False):
    st.dataframe(
        filtered.sort_values("data_vencimento"),
        use_container_width=True
    )

open_outcomes = active_outcomes[active_outcomes["saldo"] > 0].sort_values(
    "data_vencimento")

id_to_label = {
    row["id"]: f'{utils.format_date_br(row["data_vencimento"])} | {row["descricao"]} ({utils.format_brl(row["saldo"])})'
    for _, row in open_outcomes.iterrows()
}

open_outcomes_filtered = filtered[filtered["status"].str.lower() != "pago"]
selected_id = st.selectbox(
    "Conta",
    options=open_outcomes_filtered["id"].tolist(),
    format_func=lambda x: id_to_label.get(x)
)

filtered_outcome = open_outcomes[open_outcomes["id"] == selected_id]

outcome = None

if filtered_outcome.empty:
    st.warning("Não há contas a pagar para os filtros selecionados!")

else:
    outcome = filtered_outcome.iloc[0]

tab1, tab2, tab3, tab4 = st.tabs(
    ["Criar conta", "Registrar Pagamento", "Editar conta", "Deletar conta"])

with tab1:

    st.subheader("➕ Nova Conta")

    # Select tipo OUTSIDE the form so it triggers reruns
    tipo = st.selectbox("Tipo", outcomes_types, key="new_outcome_tipo")

    # ALL INPUTS OUTSIDE THE FORM
    descricao = st.text_input("Descrição", key="new_outcome_descricao")
    data_vencimento = st.date_input(
        "Data de vencimento", key="new_outcome_data_vencimento")
    quem_pagar = st.text_input("Quem pagar", key="new_outcome_quem_pagar")

    is_quote = st.checkbox("É orçamento?", key="new_outcome_is_quote")

    if is_quote:
        quote_id = st.selectbox(
            "Orçamento",
            options=[""] + list(orcamentos_map.keys()),
            format_func=lambda x: "Selecione..." if x == "" else orcamentos_map.get(
                x, x),
            key="new_outcome_orcamento"
        )
        cliente_id = ""
    else:
        cliente_id = st.selectbox(
            "Cliente",
            options=[""] + list(clientes_map.keys()),
            format_func=lambda x: "Selecione..." if x == "" else clientes_map.get(
                x, x),
            key="new_outcome_cliente"
        )
        quote_id = ""

    is_recurrent = st.checkbox(
        "É recorrente (mensal)?", key="new_outcome_is_recurrent")
    recurrence_end_date = None
    if is_recurrent:
        recurrence_end_date = st.date_input(
            "Data de término da recorrência",
            value=pd.to_datetime(data_vencimento) + relativedelta(months=12),
            key="new_outcome_recurrence_end"
        )

    # Calculate KM and valor outside form
    km = 0.0
    km_rate = 0.0
    valor = 0.0

    if tipo in ["Utilização Carro", "Utilização Moto"]:
        client_km = 0.0
        client_row = clientes[clientes["id"] ==
                              cliente_id] if is_quote == False else orcamentos[orcamentos["id"] == quote_id]
        if not client_row.empty:
            client_km = float(client_row.iloc[0].get("km", 0) or 0)

        usar_km_cliente = st.checkbox(
            "Utilizar endereço de cliente",
            value=(client_km > 0),
            key="use_client_km"
        )

        if usar_km_cliente and client_km > 0:
            km = st.number_input(
                "KM",
                min_value=0.0,
                value=client_km,
                disabled=True,
                key="outcome_km"
            )
        else:
            if usar_km_cliente and client_km == 0:
                st.warning(
                    "Cliente não possui KM cadastrado. Informe manualmente ou selecione um cliente.")
            km = st.number_input(
                "KM",
                min_value=0.0,
                value=client_km if client_km > 0 else 0.0,
                key="outcome_km"
            )

        if tipo == "Utilização Carro":
            km_rate = valor_km_carro
        else:
            km_rate = valor_km_moto

        st.caption(f"Valor por KM atual: {utils.format_brl(km_rate)}")
        valor = round(km * km_rate, 2)
        st.markdown(f"**Valor calculado:** {utils.format_brl(valor)}")
    else:
        valor = st.number_input("Valor", min_value=0.0,
                                key="new_outcome_valor")

    # Form ONLY for submission
    with st.form("new_outcome"):
        submitted = st.form_submit_button("Salvar")

        if submitted:
            base_outcome = {
                "id": str(uuid.uuid4()),
                "descricao": descricao,
                "valor": valor,
                "data_vencimento": to_iso_date(data_vencimento),
                "tipo": tipo,
                "quem_pagar": quem_pagar,
                "client_id": cliente_id,
                "quote_id": quote_id,
                "km": km if tipo in ["Utilização Carro", "Utilização Moto"] else "",
                "km_rate": km_rate if tipo in ["Utilização Carro", "Utilização Moto"] else "",
                "is_recurrent": is_recurrent,
                "recurrence_end_date": to_iso_date(recurrence_end_date) if is_recurrent else "",
                "active": True
            }

            if is_recurrent and recurrence_end_date:
                outcomes_to_save = create_recurrent_outcomes(
                    base_outcome, data_vencimento, recurrence_end_date)
                new_df = pd.concat([outcomes, pd.DataFrame(
                    outcomes_to_save)], ignore_index=True)
            else:
                new_df = pd.concat([outcomes, pd.DataFrame(
                    [base_outcome])], ignore_index=True)

            new_df["data_vencimento"] = pd.to_datetime(
                new_df["data_vencimento"]).dt.strftime("%Y-%m-%d")

            new_df = normalize_dates_for_sheets(new_df)

            utils.save_sheet(FILE_ID, "OUTCOMES_DB", new_df)

            st.success("Conta criada!" +
                       (" (com recorrência mensal)" if is_recurrent else ""))
            st.rerun()

with tab2:

    st.subheader("💰 Registrar pagamento")

    if outcome is not None:
        with st.form("pay_outcome"):
            auto_fill = st.checkbox(
                "Auto preencher com valor pendente e data de vencimento",
                value=True
            )

            default_valor = float(outcome["saldo"]) if auto_fill else 0.0
            default_data = (
                pd.to_datetime(outcome["data_vencimento"]).date()
                if auto_fill else pd.Timestamp.today().date()
            )

            valor = st.number_input(
                "Valor pago",
                min_value=0.0,
                value=default_valor
            )
            data = st.date_input(
                "Data pagamento",
                value=default_data
            )

            submitted = st.form_submit_button("Salvar")

            if submitted:
                add_payment(FILE_ID, payments, selected_id, valor, data)
                st.success("Pagamento registrado!")
                st.rerun()
    else:
        st.info("Selecione uma conta a pagar para registrar pagamento")

with tab3:

    st.subheader("✏️ Editar")

    if outcome is not None:
        # Show recurrence info
        if outcome.get("is_recurrent"):
            st.info("🔄 Esta é uma conta recorrente (mensal)")
            if outcome.get("recurrence_end_date"):
                st.caption(
                    f"Término: {utils.format_date_br(outcome['recurrence_end_date'])}")

        # Inputs OUTSIDE the form for real-time updates
        descricao = st.text_input("Descrição", outcome["descricao"])

        tipo = st.selectbox(
            "Tipo",
            outcomes_types,
            index=outcomes_types.index(outcome["tipo"]),
            key="edit_outcome_tipo"
        )

        data_vencimento = st.date_input(
            "Data de vencimento",
            value=pd.to_datetime(outcome["data_vencimento"]).date(),
            key="edit_outcome_data_vencimento"
        )

        quem_pagar = st.text_input(
            "Quem pagar",
            value=outcome.get("quem_pagar", ""),
            key="edit_outcome_quem_pagar"
        )

        is_quote = st.checkbox(
            "É orçamento?",
            value=bool(outcome.get("quote_id", "")),
            key="edit_outcome_is_quote"
        )

        if is_quote:
            quote_id = st.selectbox(
                "Orçamento",
                options=[""] + list(orcamentos_map.keys()),
                index=(
                    list([""] + list(orcamentos_map.keys())
                         ).index(outcome.get("quote_id", ""))
                    if outcome.get("quote_id", "") in [""] + list(orcamentos_map.keys())
                    else 0
                ),
                format_func=lambda x: "Selecione..." if x == "" else orcamentos_map.get(
                    x, x),
                key="edit_outcome_orcamento"
            )
            cliente_id = ""
        else:
            cliente_id = st.selectbox(
                "Cliente",
                options=[""] + list(clientes_map.keys()),
                index=(
                    list([""] + list(clientes_map.keys())
                         ).index(outcome.get("client_id", ""))
                    if outcome.get("client_id", "") in [""] + list(clientes_map.keys())
                    else 0
                ),
                format_func=lambda x: "Selecione..." if x == "" else clientes_map.get(
                    x, x),
                key="edit_outcome_cliente"
            )
            quote_id = ""

        # Recurrence editing
        is_recurrent = outcome.get("is_recurrent", False)
        recurrence_end_date = outcome.get("recurrence_end_date", "")

        if is_recurrent:
            edit_recurrence = st.checkbox(
                "Editar recorrência", key="edit_outcome_edit_recurrence")
            if edit_recurrence:
                recurrence_end_date = st.date_input(
                    "Data de término da recorrência",
                    value=pd.to_datetime(recurrence_end_date).date(
                    ) if recurrence_end_date else pd.Timestamp.today().date(),
                    key="edit_outcome_recurrence_end"
                )
                update_future = st.checkbox(
                    "Aplicar alterações às próximas ocorrências",
                    value=False,
                    key="edit_outcome_update_future"
                )
            else:
                update_future = False
        else:
            update_future = False

        if tipo in ["Utilização Carro", "Utilização Moto"]:
            km = st.number_input("KM", value=float(outcome.get("km", 0)))
            km_rate = st.number_input(
                "Valor por KM", value=float(outcome.get("km_rate", 0)))
            valor = km * km_rate
            st.markdown(f"**Valor calculado:** {utils.format_brl(valor)}")
        else:
            valor = st.number_input("Valor", value=float(outcome["valor"]))

        # Form ONLY for submission
        with st.form("edit_outcome"):
            submitted = st.form_submit_button("Salvar")

        if submitted:
            outcomes.loc[outcomes["id"] ==
                         selected_id, "descricao"] = descricao
            outcomes.loc[outcomes["id"] == selected_id, "tipo"] = tipo
            outcomes.loc[outcomes["id"] == selected_id,
                         "data_vencimento"] = data_vencimento
            outcomes.loc[outcomes["id"] ==
                         selected_id, "client_id"] = cliente_id
            outcomes.loc[outcomes["id"] == selected_id, "quote_id"] = quote_id
            outcomes.loc[outcomes["id"] ==
                         selected_id, "quem_pagar"] = quem_pagar

            if is_recurrent:
                outcomes.loc[outcomes["id"] == selected_id,
                             "recurrence_end_date"] = recurrence_end_date

            if tipo in ["Utilização Carro", "Utilização Moto"]:
                outcomes.loc[outcomes["id"] == selected_id, "km"] = km
                outcomes.loc[outcomes["id"] ==
                             selected_id, "km_rate"] = km_rate
                outcomes.loc[outcomes["id"] == selected_id, "valor"] = valor
            else:
                outcomes.loc[outcomes["id"] == selected_id, "valor"] = valor

            # If recurrent and updating future occurrences
            if is_recurrent and update_future:
                future_outcomes = outcomes[
                    (outcomes["recurrence_parent_id"] == selected_id) |
                    (outcomes["id"] == outcome.get("recurrence_parent_id", ""))
                ]

                # Update all future occurrences that are after current date
                current_outcome_date = pd.to_datetime(data_vencimento)

                for idx in future_outcomes.index:
                    future_date = pd.to_datetime(
                        outcomes.loc[idx, "data_vencimento"])
                    if future_date > current_outcome_date:
                        outcomes.loc[idx, "descricao"] = descricao
                        outcomes.loc[idx, "tipo"] = tipo
                        outcomes.loc[idx, "valor"] = valor
                        outcomes.loc[idx, "quem_pagar"] = quem_pagar
                        outcomes.loc[idx, "client_id"] = cliente_id
                        outcomes.loc[idx, "quote_id"] = quote_id
                        if tipo in ["Utilização Carro", "Utilização Moto"]:
                            outcomes.loc[idx, "km"] = km
                            outcomes.loc[idx, "km_rate"] = km_rate

            outcomes["data_vencimento"] = pd.to_datetime(
                outcomes["data_vencimento"]).dt.strftime("%Y-%m-%d")

            outcomes = normalize_dates_for_sheets(outcomes)
            utils.save_sheet(FILE_ID, "OUTCOMES_DB", outcomes)

            st.success(
                "Atualizado!" + (" (todas as próximas ocorrências atualizadas)" if is_recurrent and update_future else ""))
            st.rerun()


@st.dialog(title="Confirmar exclusão", width="small")
def confirm_delete():
    st.write(
        "Tem certeza que deseja excluir esta conta? Esta ação não pode ser desfeita.")
    st.markdown(
        f"**{utils.format_date_br(outcome['data_vencimento'])} | {outcome['descricao']} ({utils.format_brl(outcome['saldo'])})**")

    col1, col2 = st.columns(2, vertical_alignment="center")
    with col1:
        confirm = st.button("Sim, excluir", type="primary",
                            use_container_width=True)

    with col2:
        cancel = st.button("Cancelar", use_container_width=True)

    if confirm:
        outcomes.loc[outcomes["id"] == selected_id, "active"] = False

        outcomes["data_vencimento"] = pd.to_datetime(
            outcomes["data_vencimento"]).dt.strftime("%Y-%m-%d")

        outcomes = normalize_dates_for_sheets(outcomes)
        utils.save_sheet(FILE_ID, "OUTCOMES_DB", outcomes)

        st.success("Conta excluída com sucesso!")
        time.sleep(0.5)
        st.rerun()
    if cancel:
        st.info("Exclusão cancelada.")
        time.sleep(0.5)
        st.rerun()


with tab4:

    st.subheader("🗑️ Excluir conta")
    if outcome is not None:
        if st.button("Excluir", type="primary"):
            confirm_delete()

    else:
        st.info("Selecione uma conta para ser excluída!")
