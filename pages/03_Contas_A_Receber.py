import streamlit as st
import utils
import pandas as pd
import uuid
import time
import auth



st.set_page_config(page_title="Logesti - Contas a Receber",
                   page_icon=":moneybag:", layout="wide")

auth.require_login()

FILE_ID = utils.FILE_ID
# ==============================
# ENSURE IDS + SAVE
# ==============================


def ensure_income_ids(file_id, df):
    df = df.copy()

    if "id" not in df.columns:
        df["id"] = None

    mask = df["id"].isna() | (df["id"] == "")
    if mask.any():
        df.loc[mask, "id"] = [str(uuid.uuid4()) for _ in range(mask.sum())]

        # 🔥 Persist IDs immediately
        df_to_save = df.copy()
        df_to_save["data"] = df_to_save["data"].dt.strftime("%Y-%m-%d")

        utils.save_sheet(file_id, "INCOMES_DB", df_to_save)

    return df

# ==============================
# ADD FIELD: grupo_id (create + edit)
# ==============================


def generate_group_id():
    return str(uuid.uuid4())

# ==============================
# BUILD FINANCIAL VIEW (ADD GROUP LOGIC)
# ==============================


def build_financial_view(incomes, payments):
    incomes = incomes.loc[:, ~incomes.columns.duplicated()].copy()

    incomes = incomes.drop(
        columns=[
            col for col in incomes.columns if "valor_pago" in col or "income_id" in col],
        errors="ignore"
    )

    payments_grouped = (
        payments.groupby("income_id", as_index=False)["valor_pago"]
        .sum()
    )

    df = incomes.merge(
        payments_grouped,
        left_on="id",
        right_on="income_id",
        how="left"
    )

    df = df[df.get("active", True) != False]
    df = df.drop(columns=["income_id"], errors="ignore")

    df["valor_pago"] = df["valor_pago"].fillna(0)
    df["saldo"] = df["valor"] - df["valor_pago"]

    df["grupo_id"] = df.get("grupo_id", None)

    # 🔥 remove old columns before merge (fix KeyError)
    df = df.drop(columns=["total_grupo", "pago_grupo"], errors="ignore")

    group_totals = df.groupby("grupo_id").agg(
        total_grupo=("valor", "sum"),
        pago_grupo=("valor_pago", "sum")
    ).reset_index()

    df = df.merge(group_totals, on="grupo_id", how="left")

    df["saldo_grupo"] = df["total_grupo"] - df["pago_grupo"]

    def get_status(row):
        if row["saldo"] == 0:
            return "Recebido"
        elif row["valor_pago"] > 0:
            return "Recebido Parcialmente"
        return "A Receber"

    df["status"] = df.apply(get_status, axis=1)

    return df

# ==============================
# SAVE PAYMENT
# ==============================


def save_payment(file_id, payment_df):
    payment_df = payment_df.copy()

    payment_df["data_pagamento"] = pd.to_datetime(
        payment_df["data_pagamento"]
    ).dt.strftime("%Y-%m-%d")

    utils.save_sheet(file_id, "INCOMES_PAYMENTS_DB", payment_df)


# ==============================
# ADD PAYMENT
# ==============================
def add_payment(file_id, payments_df, income_id, valor, data_pagamento):
    new_payment = {
        "id": str(uuid.uuid4()),
        "income_id": income_id,
        "data_pagamento": data_pagamento,
        "valor_pago": valor
    }

    new_df = pd.concat(
        [payments_df, pd.DataFrame([new_payment])],
        ignore_index=True
    )

    save_payment(file_id, new_df)


def empty_income_rows(n=1):
    return pd.DataFrame({
        "descricao": [""] * n,
        "valor": [0.0] * n,
        "valor_recebido": [0.0] * n,
        "parcela": [""] * n,
        "client_id": [""] * n,
        "data": [pd.Timestamp.today()] * n,
        "tipo": [""] * n,
        "status": ["A Receber"] * n,
    })


if "new_incomes" not in st.session_state:
    st.session_state.new_incomes = empty_income_rows(1)


# ==============================
# GROUP PROGRESS DISPLAY
# ==============================

def render_group_progress(df, selected_id):
    if df.empty:
        return
    row = df[df["id"] == selected_id].iloc[0]

    if pd.isna(row.get("grupo_id")) or row["grupo_id"] == "":
        return

    total = row["total_grupo"]
    pago = row["pago_grupo"]

    progresso = 0 if total == 0 else pago / total
    col1, col2 = st.columns(2)
    col1.metric("Redebido", utils.format_brl(pago))
    col2.metric("Total", utils.format_brl(total))

    st.progress(progresso)


# ==============================
# UI
# ==============================
st.title("💰 Contas a Receber")

# Load data
incomes = utils.load_incomes(FILE_ID)
payments = utils.load_income_payments(FILE_ID)

# Ensure IDs exist
incomes = ensure_income_ids(FILE_ID, incomes)

# Build calculated view
df = build_financial_view(incomes, payments)


clientes, orcamentos = utils.get_clientes_and_orcamentos()

clientes_map = {
    row["id"]: (
        row["nome"]
        if pd.isna(row["endereco"])
        else f'{row["nome"]} ({row["endereco"]})'
    )
    for _, row in clientes.iterrows()
    if row["active"] == True
}

# ==============================
# FILTERS
# ==============================
st.subheader("Filtros")

years = ["Todos"] + sorted(df["data"].dt.year.dropna().unique())
months = ["Todos"] + list(range(1, 13))
status_options = ["Todos", "A Receber", "Recebido Parcialmente", "Recebido"]
client_options = ["Todos"] + sorted(
    df["client_id"].dropna().unique(),
    key=lambda x: clientes_map.get(x, x)
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    ano = st.selectbox("Ano", years)

with col2:
    mes = st.selectbox("Mês", months)

with col3:
    status = st.selectbox("Status", status_options)

with col4:
    cliente = st.selectbox(
        "Cliente",
        client_options,
        format_func=lambda x: "Todos" if x == "Todos" else clientes_map.get(
            x, x)
    )

filtered = df.copy()
filtered = filtered[filtered.get("active", "TRUE") != "FALSE"]

if ano != "Todos":
    filtered = filtered[filtered["data"].dt.year == ano]

if mes != "Todos":
    filtered = filtered[filtered["data"].dt.month == mes]

if status != "Todos":
    filtered = filtered[filtered["status"] == status]

if cliente != "Todos":
    filtered = filtered[filtered["client_id"] == cliente]


# ==============================
# METRICS
# ==============================
total = filtered["valor"].sum()
recebido = filtered["valor_pago"].sum()
saldo = filtered["saldo"].sum()

k1, k2, k3 = st.columns(3)

k1.metric("Total", utils.format_brl(total))
k2.metric("Recebido", utils.format_brl(recebido))
k3.metric("A Receber", utils.format_brl(saldo))

with st.expander("Receitas em aberto nos filtros", expanded=True):
    filtered_open = filtered[filtered["saldo"] > 0].copy()
    if filtered_open.empty:
        st.write("Nenhuma receita em aberto com os filtros selecionados.")
    else:
        filtered_open = filtered_open.assign(
            cliente=filtered_open["client_id"].map(
                clientes_map).fillna(filtered_open["client_id"])
        )
        st.dataframe(
            filtered_open[
                ["descricao", "valor", "cliente", "data", "tipo", "status", "saldo"]
            ].rename(columns={
                "descricao": "Descrição",
                "valor": "Valor",
                "cliente": "Cliente",
                "data": "Data",
                "tipo": "Tipo",
                "status": "Status",
                "saldo": "Saldo"
            })
        )

# ==============================
# GLOBAL SELECT (used in tabs)
# ==============================
st.subheader("Selecionar Receita em aberto:")

open_incomes = filtered[filtered["saldo"] > 0].sort_values("data")

if open_incomes.empty:
    st.info("Nenhuma receita em aberto.")
    selected_id = None
    income = st.dataframe({"descricao": ""})
else:
    id_to_label = {
        row["id"]: f'{utils.format_date_br(row["data"])} | {row["descricao"]} - {clientes_map.get(row["client_id"], row["client_id"])} ({utils.format_brl(row["saldo"])})'
        for _, row in open_incomes.iterrows()
    }

    selected_id = st.selectbox(
        "Receita",
        options=open_incomes["id"],
        format_func=lambda x: id_to_label.get(x),
        key="global_income_select"
    )

    render_group_progress(df, selected_id)

    income = df[df["id"] == selected_id].iloc[0]

tab1, tab2, tab3, tab4 = st.tabs(
    ["Criar novo recebimento", "Lançar pagamento", "Editar Recebimento", "Deletar Recebimento"])
# ==============================
# SELECT INCOME
# ==============================

with tab1:

    st.subheader("➕ Adicionar Receitas")

    parcelar = st.checkbox("Recebimento é parcelado")

    if not parcelar:

        num_rows = st.number_input(
            "Quantas receitas deseja adicionar?", 1, 20, 1)

        with st.form("add_incomes_form"):
            incomes_data = []
            for i in range(num_rows):
                st.subheader(f"Receita {i+1}")
                descricao = st.text_input(f"Descrição {i+1}", key=f"desc_{i}")
                valor = st.number_input(
                    f"Valor {i+1}", min_value=0.0, key=f"val_{i}")
                client_id = st.selectbox(
                    f"Cliente {i+1}",
                    options=[""] + list(clientes_map.keys()),
                    format_func=lambda x: "Selecione..." if x == "" else clientes_map[x],
                    key=f"client_{i}"
                )
                data = st.date_input(f"Data {i+1}", key=f"date_{i}")
                tipo = st.selectbox(
                    f"Tipo {i+1}",
                    options=["Reembolso", "Acompanhamento", "Projeto",
                             "Administração", "Orçamento", "Perícia", "Outros"],
                    key=f"tipo_{i}"
                )
                incomes_data.append({
                    "descricao": descricao,
                    "valor": valor,
                    "client_id": client_id,
                    "data": data,
                    "tipo": tipo
                })

            submitted = st.form_submit_button("💾 Salvar Receitas")

            if submitted:
                try:
                    new_df = pd.DataFrame(incomes_data)
                    new_df["data"] = pd.to_datetime(
                        new_df["data"]).dt.strftime("%Y-%m-%d")
                    final_df = pd.concat([incomes, new_df], ignore_index=True)
                    final_df["data"] = pd.to_datetime(
                        final_df["data"]).dt.strftime("%Y-%m-%d")
                    utils.save_incomes(FILE_ID, final_df)
                    for i in range(num_rows):
                        for key in [f"desc_{i}", f"val_{i}", f"client_{i}", f"date_{i}", f"tipo_{i}"]:
                            if key in st.session_state:
                                del st.session_state[key]
                    st.success("Receitas adicionadas com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    else:
        parcelas = []
        datas = []

        description = st.text_input(
            "Descrição", placeholder="Digite uma descrição...")
        total_valor = st.number_input("Valor total", min_value=0.0)
        num_parcelas = st.number_input("Qtd parcelas", 2, 24, 2)
        tipo = st.selectbox("Tipo de receita", [
                            "Reembolso", "Acompanhamento", "Projeto", "Administração", "Orçamento", "Perícia", "Outros"])
        client_id = st.selectbox(
            "Cliente",
            options=[""] + list(clientes_map.keys()),
            format_func=lambda x: "Selecione..." if x == "" else clientes_map[x]
        )

        tipo_parcela = st.radio(
            "Tipo",
            ["Valores iguais", "Personalizado"]
        )

        base_date = st.date_input("Data inicial")

        if tipo_parcela == "Valores iguais":
            valor_parcela = round(total_valor / num_parcelas, 2)
            parcelas = [valor_parcela] * num_parcelas
        else:
            # Initialize session state keys if not present
            for i in range(num_parcelas):
                key = f"create_parc_{i}"
                if key not in st.session_state:
                    st.session_state[key] = 0.0

            # Check if auto-fill was requested and compute values BEFORE rendering
            if st.session_state.get("auto_fill_requested", False):
                filled = [st.session_state.get(
                    f"create_parc_{i}", 0.0) for i in range(num_parcelas)]
                remaining = total_valor - sum(filled)
                blanks = [i for i, v in enumerate(filled) if v == 0.0]
                if blanks and remaining > 0:
                    fill_value = round(remaining / len(blanks), 2)
                    for i in blanks:
                        st.session_state[f"create_parc_{i}"] = fill_value
                st.session_state["auto_fill_requested"] = False

            # Now render the inputs with pre-initialized values
            parcel_values = []
            for i in range(num_parcelas):
                key = f"create_parc_{i}"
                parcel_values.append(
                    st.number_input(
                        f"Parcela {i+1}",
                        min_value=0.0,
                        value=st.session_state.get(key, 0.0),
                        key=key
                    )
                )

            if st.button("Preencher parcelas restantes automaticamente"):
                st.session_state["auto_fill_requested"] = True
                st.rerun()

            parcelas = [st.session_state.get(
                f"create_parc_{i}", 0.0) for i in range(num_parcelas)]

        for i in range(num_parcelas):
            datas.append(pd.to_datetime(base_date) + pd.DateOffset(months=i))

    # ==============================
    # ADD INCOMES (WITH GROUP)
    # ==============================
    if parcelar:
        def add_incomes(file_id, existing_df, new_rows, parcelas=None, datas=None):
            new_rows = new_rows.copy()

            grupo_id = generate_group_id()

            rows = []
            for i in range(len(parcelas)):
                rows.append({
                    "id": str(uuid.uuid4()),
                    "grupo_id": grupo_id,
                    "descricao": new_rows.iloc[0]["descricao"],
                    "valor": parcelas[i],
                    "parcela": f"{i+1}/{len(parcelas)}",
                    "client_id": new_rows.iloc[0].get("client_id", ""),
                    "data": datas[i],
                    "tipo": new_rows.iloc[0].get("tipo", ""),
                    "active": "TRUE"
                })

            new_rows = pd.DataFrame(rows)

            new_rows["data"] = pd.to_datetime(
                new_rows["data"]).dt.strftime("%Y-%m-%d")

            final_df = pd.concat([existing_df, new_rows], ignore_index=True)
            final_df["data"] = pd.to_datetime(
                final_df["data"]).dt.strftime("%Y-%m-%d")

            final_df = final_df.loc[:, ~final_df.columns.duplicated()]

            utils.save_incomes(file_id, final_df)

        if st.button("💾 Salvar receitas"):
            try:

                base_df = pd.DataFrame([{
                    "descricao": description,
                    "valor": total_valor,
                    "client_id": client_id,
                    "data": base_date,
                    "tipo": tipo,
                    "active": "TRUE"
                }])

                add_incomes(
                    FILE_ID,
                    df,
                    base_df,
                    parcelas=parcelas,
                    datas=datas
                )

                for i in range(num_parcelas):
                    key = f"create_parc_{i}"
                    if key in st.session_state:
                        del st.session_state[key]

                st.success("Receitas adicionadas com sucesso!")
                st.session_state.new_incomes = empty_income_rows(1)

                st.rerun()

            except Exception as e:
                st.error(f"Erro ao salvar: {e}")


with tab2:

    # ==============================
    # ADD PAYMENT
    # ==============================
    if selected_id is not None:
        st.subheader("💰 Registrar Recebimento")

        with st.form("payment_form"):
            auto_fill = st.checkbox(
                "Auto preencher com valor pendente e data de vencimento",
                value=True
            )

            default_valor = float(income["saldo"]) if auto_fill else 0.0
            default_data = (
                pd.to_datetime(income["data"]).date()
                if auto_fill else pd.Timestamp.today().date()
            )

            valor_pago = st.number_input(
                "Valor recebido",
                min_value=0.0,
                value=default_valor
            )
            data_pagamento = st.date_input(
                "Data do Recebimento",
                value=default_data
            )

            submitted = st.form_submit_button("Salvar Recebimento")

            if submitted:
                try:
                    add_payment(FILE_ID, payments, selected_id,
                                valor_pago, data_pagamento)
                    st.success("Recebimento registrado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
    else:
        st.info("Selecione uma receita em aberto para registrar recebimento.")


with tab3:

    st.subheader("✏️ Editar Receita")

    if selected_id is not None:
        with st.form("edit_income"):
            descricao = st.text_input("Descrição", income["descricao"])
            valor = st.number_input("Valor", value=float(income["valor"]))
            client_id = st.selectbox(
                "Cliente",
                options=[""] + list(clientes_map.keys()),
                format_func=lambda x: "Selecione..." if x == "" else clientes_map[x]
            )

            parcelar_edit = st.checkbox("Recriar como parcelado")

            if parcelar_edit:
                num_parcelas = st.number_input("Qtd parcelas", 2, 24, 2)
                base_date = st.date_input("Data inicial")

            submitted = st.form_submit_button("Salvar edição")

            if submitted:
                if parcelar_edit:
                    grupo_id = generate_group_id()

                    incomes.loc[incomes["id"] == selected_id, "active"] = False

                    valor_parcela = valor / num_parcelas

                    rows = []
                    for i in range(num_parcelas):
                        rows.append({
                            "id": str(uuid.uuid4()),
                            "grupo_id": grupo_id,
                            "descricao": descricao,
                            "valor": valor_parcela,
                            "parcela": f"{i+1}/{num_parcelas}",
                            "client_id": client_id,
                            "data": pd.to_datetime(base_date) + pd.DateOffset(months=i),
                            "tipo": income["tipo"],
                            "active": True
                        })

                    new_df = pd.concat(
                        [incomes, pd.DataFrame(rows)], ignore_index=True)

                else:
                    incomes.loc[incomes["id"] ==
                                selected_id, "descricao"] = descricao
                    incomes.loc[incomes["id"] == selected_id, "valor"] = valor
                    incomes.loc[incomes["id"] ==
                                selected_id, "client_id"] = client_id

                    new_df = incomes

                new_df["data"] = pd.to_datetime(
                    new_df["data"]).dt.strftime("%Y-%m-%d")

                utils.save_sheet(FILE_ID, "INCOMES_DB", new_df)

                st.success("Atualizado!")
                st.rerun()
    else:
        st.info("Selecione uma receita para editar.")


@st.dialog(title="Confirmar exclusão de receita", width="small")
def confirm_delete_income():
    if selected_id is None:
        st.info("Selecione uma receita para excluir.")
        return

    row = df[df["id"] == selected_id].iloc[0]
    st.write(
        "Tem certeza que deseja excluir esta receita? Esta ação não pode ser desfeita.")
    st.markdown(
        f"**{utils.format_date_br(row['data'])} | {row['descricao']} ({utils.format_brl(row['saldo'])})**")

    col1, col2 = st.columns(2, vertical_alignment="center")
    with col1:
        confirm = st.button("Sim, excluir", type="primary",
                            use_container_width=True)

    with col2:
        cancel = st.button("Cancelar", use_container_width=True)

    if confirm:
        incomes.loc[incomes["id"] == selected_id, "active"] = False
        incomes["data"] = pd.to_datetime(
            incomes["data"]).dt.strftime("%Y-%m-%d")

        utils.save_sheet(FILE_ID, "INCOMES_DB", incomes)

        st.success("Receita excluída com sucesso!")
        time.sleep(0.5)
        st.rerun()
    if cancel:
        st.info("Exclusão cancelada.")
        time.sleep(0.5)
        st.rerun()


with tab4:
    if selected_id is not None:
        if st.button("🗑️ Excluir receita"):
            confirm_delete_income()
    else:
        st.info("Selecione uma receita para excluir.")
