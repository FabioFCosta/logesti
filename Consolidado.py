import streamlit as st
import pandas as pd
import utils
import plotly.graph_objects as go
import plotly.express as px
import auth


st.set_page_config(page_title="Logesti - Consolidado", page_icon=":bar_chart:", layout="wide")
auth.require_login()
st.title("Consolidado")
st.subheader("Visão geral das receitas, despesas e lucros por cliente")

incomes = utils.load_incomes(utils.FILE_ID)
outcomes=utils.load_outcomes(utils.FILE_ID)
outcomes_payments = utils.load_outcome_payments(utils.FILE_ID)
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

consolidated_by_client = pd.DataFrame()

for _, row in clientes.iterrows():
    income_sum = incomes[incomes["cliente_nome"] == row['nome']]["valor"].sum()
    outcome_sum = outcomes[outcomes["cliente_nome"] == row['nome']]["valor"].sum()
    if row['nome'] == "":
        continue
    if row['nome'] not in incomes["cliente_nome"].unique() and row['nome'] not in outcomes["cliente_nome"].unique():
        continue
  
    pro_labore = outcomes[outcomes["cliente_nome"] == row['nome']].loc[outcomes["tipo"] == "Pro Labore"]["valor"].sum()
    outcome_sum = outcome_sum - pro_labore
    profit = income_sum - outcome_sum
    consolidated_by_client = pd.concat([consolidated_by_client, pd.DataFrame({
        "cliente_nome": [row['nome']],
        "incomes": [income_sum],
        "outcomes": [outcome_sum],
        "profit": [profit],
        "pro-labore": [pro_labore],
        "caixa":[profit-pro_labore]
    })], ignore_index=True)

for _, row in orcamentos.iterrows():
    if row['nome'] == "":
        continue
    if row['nome'] not in incomes["cliente_nome"].unique() and row['nome'] not in outcomes["cliente_nome"].unique():
        continue
    if row['nome'] in consolidated_by_client["cliente_nome"].values:
        continue
    
    income_sum = incomes[incomes["cliente_nome"] == row['nome']]["valor"].sum()
    outcome_sum = outcomes[outcomes["cliente_nome"] == row['nome']]["valor"].sum()
  
    pro_labore = outcomes[outcomes["cliente_nome"] == row['nome']].loc[outcomes["tipo"] == "Pro Labore"]["valor"].sum()
    outcome_sum = outcome_sum - pro_labore
    profit = income_sum - outcome_sum
    consolidated_by_client = pd.concat([consolidated_by_client, pd.DataFrame({
        "cliente_nome": [row['nome']],
        "incomes": [income_sum],
        "outcomes": [outcome_sum],
        "profit": [profit],
        "pro-labore": [pro_labore],
        "caixa":[profit-pro_labore]
    })], ignore_index=True)



col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Receitas", f"R$ {consolidated_by_client['incomes'].sum():,.2f}")
with col2:
    st.metric("Total Despesas", f"R$ {consolidated_by_client['outcomes'].sum():,.2f}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Lucro Total", f"R$ {consolidated_by_client['profit'].sum():,.2f}")
with col2:
    st.metric("Pro Labore Total", f"R$ {consolidated_by_client['pro-labore'].sum():,.2f}")
with col3:
    st.metric("Caixa Total", f"R$ {consolidated_by_client['caixa'].sum():,.2f}")
    
with st.expander("Consolidado por cliente", False):
    st.dataframe(consolidated_by_client, use_container_width=True)

consolidated=pd.DataFrame()
for _, row in outcomes[(outcomes["cliente_nome"].isna())].iterrows():
    outcome_id=row["id"]
    payment = outcomes_payments[outcomes_payments["outcome_id"] == outcome_id]
    if payment.empty:
        continue
    consolidated = pd.concat([consolidated, pd.DataFrame({
        "descricao": [row["descricao"]],
        "valor": [row["valor"]],
        "data_vencimento": [row["data_vencimento"]],
        "tipo": [row["tipo"]],
        "quem_pagar": [row["quem_pagar"]],
        "data_pagamento": [payment["data_pagamento"].iloc[0] if not payment.empty else None],
    })], ignore_index=True)
    

caixa_total = consolidated_by_client['caixa'].sum()
despesa_total = consolidated['valor'].sum()

st.subheader("Visão das despesas da empresa")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Caixa Total", f"R$ {caixa_total:,.2f}")
with col2:
    st.metric("Despesa Total", f"R$ {despesa_total:,.2f}")
with col3:
    st.metric("Caixa Atual", f"R$ {caixa_total-despesa_total:,.2f}")
with st.expander("Despesas da empresa", False):
    st.dataframe(consolidated, use_container_width=True)

# Charts Section
st.divider()
st.subheader("📊 Análises Visuais")

# Prepare data for charts
incomes_with_date = incomes[incomes['data'].notna()].copy()
outcomes_with_date = outcomes[outcomes['data_vencimento'].notna()].copy()

# Add month-year columns for grouping
incomes_with_date['mes_ano'] = incomes_with_date['data'].dt.to_period('M')
outcomes_with_date['mes_ano'] = outcomes_with_date['data_vencimento'].dt.to_period('M')

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
st.subheader("2️⃣ Despesas da Empresa (Caixa vs Demais) por Mês")
enterprise_outcomes = outcomes_with_date[(outcomes_with_date['cliente_nome'].isna()) | (outcomes_with_date['cliente_nome'] == '')].copy()
caixa_outcome_by_month = enterprise_outcomes[enterprise_outcomes['quem_pagar'] == 'CAIXA'].groupby('mes_ano')['valor'].sum()
other_outcome_by_month = enterprise_outcomes[enterprise_outcomes['quem_pagar'] != 'CAIXA'].groupby('mes_ano')['valor'].sum()

all_months_enterprise = caixa_outcome_by_month.index.union(other_outcome_by_month.index)
caixa_outcome_by_month = caixa_outcome_by_month.reindex(all_months_enterprise, fill_value=0)
other_outcome_by_month = other_outcome_by_month.reindex(all_months_enterprise, fill_value=0)

df_enterprise_monthly = pd.DataFrame({
    'Mês': [str(m) for m in all_months_enterprise],
    'Caixa': caixa_outcome_by_month.values,
    'Outros': other_outcome_by_month.values
})

fig_enterprise_monthly = go.Figure()
fig_enterprise_monthly.add_trace(go.Bar(x=df_enterprise_monthly['Mês'], y=df_enterprise_monthly['Caixa'], name='Caixa', marker_color='orange'))
fig_enterprise_monthly.add_trace(go.Bar(x=df_enterprise_monthly['Mês'], y=df_enterprise_monthly['Outros'], name='Outras Despesas', marker_color='purple'))
fig_enterprise_monthly.update_layout(barmode='group', title='Despesas da Empresa por Mês', xaxis_title='Mês', yaxis_title='Valor (R$)', height=400, hovermode='x unified')
st.plotly_chart(fig_enterprise_monthly, use_container_width=True)

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