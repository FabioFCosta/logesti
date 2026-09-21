import streamlit as st
import pandas as pd
import utils
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Logesti - Consolidado", page_icon=":bar_chart:", layout="wide")
st.title("Consolidado")
st.subheader("Visão geral das receitas, despesas e lucros por cliente")

incomes = utils.load_incomes(utils.FILE_ID)
outcomes=utils.load_outcomes(utils.FILE_ID)
outcomes_payments = utils.load_outcome_payments(utils.FILE_ID)
income_payments = utils.load_income_payments(utils.FILE_ID)
clientes,orcamentos = utils.get_clientes_and_orcamentos()

def get_client_name(income):
    if pd.isna(income.get("quote_id")) and pd.isna(income.get("client_id")):
        return ""
    if income.get("client_id"):
        cliente = clientes.loc[clientes["id"] == income["client_id"]]
        if not cliente.empty:
            return cliente.iloc[0]["nome"]
        else:
            return ""
    if income.get("quote_id"):
        orcamento = orcamentos.loc[orcamentos["id"] == income["quote_id"]]
        print(income["quote_id"])
        if not orcamento.empty:
            return orcamento.iloc[0]["nome"]
        else:
            return ""

incomes["cliente_nome"] = incomes.apply(get_client_name, axis=1)
outcomes["cliente_nome"] = outcomes.apply(get_client_name, axis=1)

# Registros ativos (soft-delete via coluna "active"). A coluna vem da Sheets
# API como string ("TRUE"/"FALSE"), não bool — comparar com `!= False` nunca
# filtra nada (mesmo padrão de pages/04_Contas_A_Pagar.py linha 187).
def _filter_active(df):
    if "active" not in df.columns:
        return df
    return df[df["active"].astype(str).str.upper() != "FALSE"]

incomes_active = _filter_active(incomes).copy()
outcomes_active = _filter_active(outcomes).copy()

consolidated_by_client = pd.DataFrame()

for _, row in clientes.iterrows():
    if row['nome'] == "":
        continue
    if row['nome'] not in incomes_active["cliente_nome"].unique() and row['nome'] not in outcomes_active["cliente_nome"].unique():
        continue

    client_income_ids = incomes_active[incomes_active["cliente_nome"] == row['nome']]["id"]
    income_sum = income_payments[income_payments["income_id"].isin(client_income_ids)]["valor_pago"].sum()

    client_outcomes = outcomes_active[outcomes_active["cliente_nome"] == row['nome']]
    client_outcome_ids = client_outcomes[client_outcomes["tipo"] != "Pro Labore"]["id"]
    outcome_sum = outcomes_payments[outcomes_payments["outcome_id"].isin(client_outcome_ids)]["valor_pago"].sum()

    profit = income_sum - outcome_sum
    consolidated_by_client = pd.concat([consolidated_by_client, pd.DataFrame({
        "cliente_nome": [row['nome']],
        "incomes": [income_sum],
        "outcomes": [outcome_sum],
        "profit": [profit],
    })], ignore_index=True)

for _, row in orcamentos[orcamentos["active"] == True].iterrows():
    if row['nome'] == "":
        continue
    if row['nome'] not in incomes_active["cliente_nome"].unique() and row['nome'] not in outcomes_active["cliente_nome"].unique():
        continue
    if row['nome'] in consolidated_by_client["cliente_nome"].values:
        continue

    client_income_ids = incomes_active[incomes_active["cliente_nome"] == row['nome']]["id"]
    income_sum = income_payments[income_payments["income_id"].isin(client_income_ids)]["valor_pago"].sum()

    client_outcomes = outcomes_active[outcomes_active["cliente_nome"] == row['nome']]
    client_outcome_ids = client_outcomes[client_outcomes["tipo"] != "Pro Labore"]["id"]
    outcome_sum = outcomes_payments[outcomes_payments["outcome_id"].isin(client_outcome_ids)]["valor_pago"].sum()

    profit = income_sum - outcome_sum
    consolidated_by_client = pd.concat([consolidated_by_client, pd.DataFrame({
        "cliente_nome": [row['nome']],
        "incomes": [income_sum],
        "outcomes": [outcome_sum],
        "profit": [profit],

    })], ignore_index=True)

consolidated_by_client["profit_pct"] = consolidated_by_client.apply(
    lambda r: (r["profit"] / r["incomes"] * 100) if r["incomes"] else None,
    axis=1
)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #2e7d32;">
            <p style="margin: 0; font-size: 14px; color: #555;">Total Receitas</p>
            <h2 style="margin: 0; color: #2e7d32; font-size: 28px; font-weight: bold;">R$ {consolidated_by_client['incomes'].sum():,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #c62828;">
            <p style="margin: 0; font-size: 14px; color: #555;">Total Despesas</p>
            <h2 style="margin: 0; color: #c62828; font-size: 28px; font-weight: bold;">R$ {consolidated_by_client['outcomes'].sum():,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #666;">
            <p style="margin: 0; font-size: 14px; color: #555;">Lucro Total</p>
            <h2 style="margin: 0; color: #333; font-size: 28px; font-weight: bold;">R$ {consolidated_by_client['profit'].sum():,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

st.write("")

with st.expander("Consolidado por cliente", False):
    st.dataframe(consolidated_by_client, use_container_width=True)

consolidated = pd.DataFrame()
enterprise_outcomes_for_summary = outcomes_active[
    outcomes_active["cliente_nome"].apply(lambda x: pd.isna(x) or str(x).strip() == "")
].copy()

for _, row in enterprise_outcomes_for_summary.iterrows():
    outcome_id = row["id"]
    payment = outcomes_payments[outcomes_payments["outcome_id"] == outcome_id]
    consolidated = pd.concat([consolidated, pd.DataFrame({
        "descricao": [row["descricao"]],
        "valor": [row["valor"]],
        "data_vencimento": [row["data_vencimento"]],
        "tipo": [row["tipo"]],
        "quem_pagar": [row["quem_pagar"]],
        "data_pagamento": [payment["data_pagamento"].iloc[0] if not payment.empty else None],
    })], ignore_index=True)


enterprise_outcomes_no_pl_ids = enterprise_outcomes_for_summary[
    enterprise_outcomes_for_summary["tipo"] != "Pro Labore"
]["id"]
despesa_total = outcomes_payments[outcomes_payments["outcome_id"].isin(enterprise_outcomes_no_pl_ids)]["valor_pago"].sum()

pro_labore_ids = outcomes_active[outcomes_active["tipo"] == "Pro Labore"]["id"]
pro_labore_total = outcomes_payments[outcomes_payments["outcome_id"].isin(pro_labore_ids)]["valor_pago"].sum()

caixa_total = consolidated_by_client['profit'].sum() - despesa_total - pro_labore_total

st.subheader("Visão das despesas da empresa")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #1565c0;">
            <p style="margin: 0; font-size: 14px; color: #555;">Caixa Total</p>
            <h2 style="margin: 0; color: #1565c0; font-size: 28px; font-weight: bold;">R$ {caixa_total:,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #c62828;">
            <p style="margin: 0; font-size: 14px; color: #555;">Despesa Total</p>
            <h2 style="margin: 0; color: #c62828; font-size: 28px; font-weight: bold;">R$ {despesa_total:,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #666;">
            <p style="margin: 0; font-size: 14px; color: #555;">Pro Labore Total</p>
            <h2 style="margin: 0; color: #333; font-size: 28px; font-weight: bold;">R$ {pro_labore_total:,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

st.write("")

with st.expander("Despesas da empresa", False):
    st.dataframe(consolidated, use_container_width=True)

# Seção: Receitas e Despesas Futuras
st.divider()
st.subheader("Receitas e Despesas Futuras")

data_limite = st.date_input(
    "Data limite",
    value=(pd.Timestamp.today() + pd.DateOffset(months=1)).date()
)

hoje = pd.Timestamp.today().normalize()
data_limite_ts = pd.Timestamp(data_limite)

income_payments_grouped = income_payments.groupby("income_id")["valor_pago"].sum()
incomes_future = incomes_active.copy()
incomes_future["valor_pago"] = incomes_future["id"].map(income_payments_grouped).fillna(0)
incomes_future["saldo"] = incomes_future["valor"] - incomes_future["valor_pago"]
incomes_future = incomes_future[
    (incomes_future["saldo"] > 0) &
    (incomes_future["data"] >= hoje) &
    (incomes_future["data"] <= data_limite_ts)
]
recebimentos_futuros = incomes_future["saldo"].sum()

outcomes_payments_grouped = outcomes_payments.groupby("outcome_id")["valor_pago"].sum()
outcomes_future = outcomes_active.copy()
outcomes_future["valor_pago"] = outcomes_future["id"].map(outcomes_payments_grouped).fillna(0)
outcomes_future["saldo"] = outcomes_future["valor"] - outcomes_future["valor_pago"]
outcomes_future = outcomes_future[
    (outcomes_future["saldo"] > 0) &
    (outcomes_future["data_vencimento"] >= hoje) &
    (outcomes_future["data_vencimento"] <= data_limite_ts)
]
pagamentos_futuros = outcomes_future["saldo"].sum()

caixa_futuro = recebimentos_futuros - pagamentos_futuros

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #2e7d32;">
            <p style="margin: 0; font-size: 14px; color: #555;">Recebimentos Futuros</p>
            <h2 style="margin: 0; color: #2e7d32; font-size: 28px; font-weight: bold;">R$ {recebimentos_futuros:,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #c62828;">
            <p style="margin: 0; font-size: 14px; color: #555;">Pagamentos Futuros</p>
            <h2 style="margin: 0; color: #c62828; font-size: 28px; font-weight: bold;">R$ {pagamentos_futuros:,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        f"""
        <div style="background-color: #141414; padding: 15px; border-radius: 8px; border-left: 5px solid #1565c0;">
            <p style="margin: 0; font-size: 14px; color: #555;">Caixa Futuro</p>
            <h2 style="margin: 0; color: #1565c0; font-size: 28px; font-weight: bold;">R$ {caixa_futuro:,.2f}</h2>
        </div>
    """,
        unsafe_allow_html=True,
    )

st.write("")

# Charts Section
st.divider()
st.subheader("📊 Análises Visuais")

# Prepare data for charts
incomes_with_date = incomes[incomes['data'].notna()].copy()
outcomes_with_date = outcomes[outcomes['data_vencimento'].notna()].copy()

# Add month-year columns for grouping
incomes_with_date['mes_ano'] = incomes_with_date['data'].dt.to_period('M')
outcomes_with_date['mes_ano'] = outcomes_with_date['data_vencimento'].dt.to_period('M')

# Use payment dates for enterprise expenses when available
enterprise_outcomes = outcomes_with_date[
    outcomes_with_date['cliente_nome'].apply(lambda x: pd.isna(x) or str(x).strip() == '')
].copy()
if 'data_pagamento' in consolidated.columns:
    enterprise_outcomes['payment_date'] = pd.to_datetime(consolidated['data_pagamento'], errors='coerce')
else:
    enterprise_outcomes['payment_date'] = pd.NaT
enterprise_outcomes['mes_ano'] = pd.to_datetime(
    enterprise_outcomes['payment_date'].fillna(enterprise_outcomes['data_vencimento'])
).dt.to_period('M')

# 1. Client Incomes and Outcomes by Month
st.subheader("1️⃣ Receitas e Despesas dos Clientes por Mês")
client_income_by_month = incomes_with_date[incomes_with_date['cliente_nome'].notna() & (incomes_with_date['cliente_nome'] != '')].groupby('mes_ano')['valor'].sum()
client_outcome_by_month = outcomes_with_date[outcomes_with_date['cliente_nome'].notna() & (outcomes_with_date['cliente_nome'] != '')].groupby('mes_ano')['valor'].sum()

# Ensure both series have the same index
all_months = client_income_by_month.index.union(client_outcome_by_month.index)
client_income_by_month = client_income_by_month.reindex(all_months, fill_value=0)
client_outcome_by_month = client_outcome_by_month.reindex(all_months, fill_value=0)

df_client_monthly = pd.DataFrame({
    'Mês': [str(m) for m in all_months],
    'Receitas': client_income_by_month.values,
    'Despesas': client_outcome_by_month.values
})

fig_client_monthly = go.Figure()
fig_client_monthly.add_trace(go.Bar(x=df_client_monthly['Mês'], y=df_client_monthly['Receitas'], name='Receitas', marker_color='green'))
fig_client_monthly.add_trace(go.Bar(x=df_client_monthly['Mês'], y=df_client_monthly['Despesas'], name='Despesas', marker_color='red'))
fig_client_monthly.update_layout(barmode='group', title='Receitas e Despesas dos Clientes por Mês', xaxis_title='Mês', yaxis_title='Valor (R$)', height=400, hovermode='x unified')
st.plotly_chart(fig_client_monthly, use_container_width=True)

# 2. Caixa and Enterprise Outcomes by Month
st.subheader("1️⃣ Receitas e Despesas Gerais por Mês")
client_income_by_month = incomes_with_date[incomes_with_date['cliente_nome'].notna() & (incomes_with_date['cliente_nome'] != '')].groupby('mes_ano')['valor'].sum()
outcome_by_month = outcomes_with_date.groupby('mes_ano')['valor'].sum()

# Ensure both series have the same index
all_months = client_income_by_month.index.union(outcome_by_month.index)
client_income_by_month = client_income_by_month.reindex(all_months, fill_value=0)
outcome_by_month = outcome_by_month.reindex(all_months, fill_value=0)

df_client_monthly = pd.DataFrame({
    'Mês': [str(m) for m in all_months],
    'Receitas': client_income_by_month.values,
    'Despesas': outcome_by_month.values
})

fig_client_monthly = go.Figure()
fig_client_monthly.add_trace(go.Bar(x=df_client_monthly['Mês'], y=df_client_monthly['Receitas'], name='Receitas', marker_color='green'))
fig_client_monthly.add_trace(go.Bar(x=df_client_monthly['Mês'], y=df_client_monthly['Despesas'], name='Despesas', marker_color='red'))
fig_client_monthly.update_layout(barmode='group', title='Receitas e Despesas Gerais por Mês', xaxis_title='Mês', yaxis_title='Valor (R$)', height=400, hovermode='x unified')
st.plotly_chart(fig_client_monthly, use_container_width=True)

# Create columns for pie charts
col1, col2 = st.columns(2)

# 3. Pie chart - Incomes by Type
with col1:
    st.subheader("3️⃣ Receitas por Tipo")
    if 'tipo' in incomes_with_date.columns:
        income_by_type = incomes_with_date.groupby('tipo')['valor'].sum()
        fig_income_type = go.Figure(data=[go.Pie(labels=income_by_type.index, values=income_by_type.values)])
        fig_income_type.update_layout(title='Distribuição de Receitas por Tipo', height=400)
        st.plotly_chart(fig_income_type, use_container_width=True)
    else:
        st.info("Dados de tipo de receita não disponíveis")

# 4. Pie chart - Client Outcomes by Type
with col2:
    st.subheader("4️⃣ Despesas de Clientes por Tipo")
    client_outcomes = outcomes_with_date[(outcomes_with_date['cliente_nome'].notna()) & (outcomes_with_date['cliente_nome'] != '')]
    if not client_outcomes.empty and 'tipo' in client_outcomes.columns:
        outcome_client_by_type = client_outcomes.groupby('tipo')['valor'].sum()
        fig_outcome_client_type = go.Figure(data=[go.Pie(labels=outcome_client_by_type.index, values=outcome_client_by_type.values)])
        fig_outcome_client_type.update_layout(title='Distribuição de Despesas de Clientes por Tipo', height=400)
        st.plotly_chart(fig_outcome_client_type, use_container_width=True)
    else:
        st.info("Dados de despesas de clientes não disponíveis")

# 5. Pie chart - Enterprise Outcomes by Type
st.subheader("5️⃣ Despesas da Empresa por Tipo")
if not enterprise_outcomes.empty and 'tipo' in enterprise_outcomes.columns:
    outcome_enterprise_by_type = enterprise_outcomes.groupby('tipo')['valor'].sum()
    fig_outcome_enterprise_type = go.Figure(data=[go.Pie(labels=outcome_enterprise_by_type.index, values=outcome_enterprise_by_type.values)])
    fig_outcome_enterprise_type.update_layout(title='Distribuição de Despesas da Empresa por Tipo', height=400)
    st.plotly_chart(fig_outcome_enterprise_type, use_container_width=True)
else:
    st.info("Dados de despesas da empresa não disponíveis")

# 6. Bar chart - Profit % by Client
st.subheader("6️⃣ % de Lucro por Cliente")
profit_pct_df = consolidated_by_client[consolidated_by_client["profit_pct"].notna()].copy()
profit_pct_df = profit_pct_df.sort_values("profit_pct", ascending=False)
if not profit_pct_df.empty:
    colors = ["green" if v >= 0 else "red" for v in profit_pct_df["profit_pct"]]
    fig_profit_pct = go.Figure()
    fig_profit_pct.add_trace(go.Bar(
        x=profit_pct_df["cliente_nome"],
        y=profit_pct_df["profit_pct"],
        marker_color=colors,
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>"
    ))
    fig_profit_pct.update_layout(
        title="% de Lucro por Cliente (Lucro / Receita)",
        xaxis_title="Cliente",
        yaxis_title="% Lucro",
        height=400
    )
    st.plotly_chart(fig_profit_pct, use_container_width=True)
else:
    st.info("Sem clientes com receita lançada para calcular % de lucro")
