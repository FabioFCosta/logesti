"""
Testa a lógica do "caixa acumulado" mensal adicionada ao gráfico "Receitas e
Despesas Gerais por Mês" em `Consolidado.py` (tarefa
linha-caixa-grafico-receitas-despesas): soma de pagamentos reais
(income_payments/outcomes_payments) de registros ativos, agrupada por mês de
`data_pagamento`, acumulada via `cumsum`, e realinhada ao eixo X das barras
(mês de vencimento) via `reindex` + `ffill` + `fillna(0)`.

`Consolidado.py` é um script Streamlit com efeitos colaterais no nível do
módulo (autenticação Google, leitura da planilha) -- importar o módulo
inteiro executaria isso. O bloco de cálculo do caixa não está isolado numa
função (é código de script inline), então extraímos o trecho de origem
diretamente do arquivo via marcadores de texto únicos e o executamos isolado
com dataframes de entrada sintéticos, sem duplicar a fórmula manualmente --
o texto testado é exatamente o que está no arquivo.
"""
import os

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLIDADO_PATH = os.path.join(REPO_ROOT, "Consolidado.py")

START_MARKER = 'st.subheader("1️⃣ Receitas e Despesas Gerais por Mês")'
END_MARKER = (
    "caixa_acumulado_by_month = "
    "caixa_acumulado_by_month.reindex(all_months).ffill().fillna(0)"
)


def _load_caixa_block():
    with open(CONSOLIDADO_PATH, encoding="utf-8") as f:
        source = f.read()

    start = source.index(START_MARKER)
    start = source.index("\n", start) + 1  # pula a linha do st.subheader em si
    end = source.index(END_MARKER, start)
    end = source.index("\n", end) + 1  # inclui a linha inteira do end marker

    return source[start:end]


CAIXA_BLOCK_SOURCE = _load_caixa_block()


def _run_caixa_block(incomes_with_date, outcomes_with_date, income_payments,
                      outcomes_payments, incomes_active, outcomes_active):
    namespace = {
        "pd": pd,
        "incomes_with_date": incomes_with_date,
        "outcomes_with_date": outcomes_with_date,
        "income_payments": income_payments,
        "outcomes_payments": outcomes_payments,
        "incomes_active": incomes_active,
        "outcomes_active": outcomes_active,
    }
    exec(CAIXA_BLOCK_SOURCE, namespace)
    return namespace["caixa_acumulado_by_month"], namespace["all_months"]


def _empty_incomes_with_date():
    return pd.DataFrame({
        "cliente_nome": pd.Series(dtype="object"),
        "mes_ano": pd.Series(dtype="object"),
        "valor": pd.Series(dtype="float"),
    })


def _empty_outcomes_with_date():
    return pd.DataFrame({
        "mes_ano": pd.Series(dtype="object"),
        "valor": pd.Series(dtype="float"),
    })


def test_caixa_acumulado_cumsum_basico():
    # Jan: recebe 1000, paga 400 -> saldo 600
    # Fev: recebe 500, paga 200 -> saldo 900 (600 + 300)
    incomes_active = pd.DataFrame({"id": ["i1", "i2"]})
    outcomes_active = pd.DataFrame({"id": ["o1", "o2"]})

    income_payments = pd.DataFrame({
        "income_id": ["i1", "i2"],
        "data_pagamento": pd.to_datetime(["2025-01-10", "2025-02-05"]),
        "valor_pago": [1000.0, 500.0],
    })
    outcomes_payments = pd.DataFrame({
        "outcome_id": ["o1", "o2"],
        "data_pagamento": pd.to_datetime(["2025-01-15", "2025-02-20"]),
        "valor_pago": [400.0, 200.0],
    })

    caixa, all_months = _run_caixa_block(
        _empty_incomes_with_date(), _empty_outcomes_with_date(),
        income_payments, outcomes_payments, incomes_active, outcomes_active,
    )

    jan = pd.Period("2025-01", freq="M")
    fev = pd.Period("2025-02", freq="M")
    assert caixa[jan] == 600.0
    assert caixa[fev] == 900.0


def test_caixa_acumulado_ignora_registros_inativos():
    # income_id "i2" não está em incomes_active -> não deve entrar na soma.
    incomes_active = pd.DataFrame({"id": ["i1"]})
    outcomes_active = pd.DataFrame({"id": []})

    income_payments = pd.DataFrame({
        "income_id": ["i1", "i2"],
        "data_pagamento": pd.to_datetime(["2025-01-10", "2025-01-12"]),
        "valor_pago": [1000.0, 9999.0],
    })
    outcomes_payments = pd.DataFrame({
        "outcome_id": pd.Series(dtype="object"),
        "data_pagamento": pd.Series(dtype="datetime64[ns]"),
        "valor_pago": pd.Series(dtype="float"),
    })

    caixa, _ = _run_caixa_block(
        _empty_incomes_with_date(), _empty_outcomes_with_date(),
        income_payments, outcomes_payments, incomes_active, outcomes_active,
    )

    jan = pd.Period("2025-01", freq="M")
    assert caixa[jan] == 1000.0


def test_caixa_acumulado_ffill_em_meses_sem_pagamento_novo():
    # Pagamento só em Jan; Mar aparece no eixo X por causa de despesa de
    # vencimento (outcomes_with_date) sem pagamento correspondente em Mar
    # (Fev não entra no eixo X porque não há receita/despesa de vencimento
    # nem pagamento em Fev -- all_months só inclui meses com algum dado).
    # O saldo de Jan deve ser carregado (ffill) pra Mar.
    incomes_active = pd.DataFrame({"id": ["i1"]})
    outcomes_active = pd.DataFrame({"id": []})

    income_payments = pd.DataFrame({
        "income_id": ["i1"],
        "data_pagamento": pd.to_datetime(["2025-01-10"]),
        "valor_pago": [1000.0],
    })
    outcomes_payments = pd.DataFrame({
        "outcome_id": pd.Series(dtype="object"),
        "data_pagamento": pd.Series(dtype="datetime64[ns]"),
        "valor_pago": pd.Series(dtype="float"),
    })

    outcomes_with_date = pd.DataFrame({
        "mes_ano": [pd.Period("2025-03", freq="M")],
        "valor": [50.0],
    })

    caixa, all_months = _run_caixa_block(
        _empty_incomes_with_date(), outcomes_with_date,
        income_payments, outcomes_payments, incomes_active, outcomes_active,
    )

    jan = pd.Period("2025-01", freq="M")
    mar = pd.Period("2025-03", freq="M")
    assert list(all_months) == [jan, mar]
    assert caixa[jan] == 1000.0
    assert caixa[mar] == 1000.0  # ffill: sem pagamento novo em Mar


def test_caixa_acumulado_zero_antes_do_primeiro_pagamento():
    # Despesa de vencimento em Jan (sem pagamento), primeiro pagamento só em
    # Fev -> Jan deve ficar em 0 (fillna), não NaN nem o saldo de Fev.
    incomes_active = pd.DataFrame({"id": ["i1"]})
    outcomes_active = pd.DataFrame({"id": []})

    income_payments = pd.DataFrame({
        "income_id": ["i1"],
        "data_pagamento": pd.to_datetime(["2025-02-10"]),
        "valor_pago": [500.0],
    })
    outcomes_payments = pd.DataFrame({
        "outcome_id": pd.Series(dtype="object"),
        "data_pagamento": pd.Series(dtype="datetime64[ns]"),
        "valor_pago": pd.Series(dtype="float"),
    })

    outcomes_with_date = pd.DataFrame({
        "mes_ano": [pd.Period("2025-01", freq="M")],
        "valor": [50.0],
    })

    caixa, _ = _run_caixa_block(
        _empty_incomes_with_date(), outcomes_with_date,
        income_payments, outcomes_payments, incomes_active, outcomes_active,
    )

    jan = pd.Period("2025-01", freq="M")
    fev = pd.Period("2025-02", freq="M")
    assert caixa[jan] == 0.0
    assert caixa[fev] == 500.0


def test_caixa_acumulado_ignora_pagamentos_sem_data():
    # data_pagamento nula (NaT) -- pagamento registrado mas ainda não pago de
    # fato -- não deve entrar na soma nem quebrar o groupby.
    incomes_active = pd.DataFrame({"id": ["i1", "i2"]})
    outcomes_active = pd.DataFrame({"id": []})

    income_payments = pd.DataFrame({
        "income_id": ["i1", "i2"],
        "data_pagamento": pd.to_datetime(["2025-01-10", None]),
        "valor_pago": [1000.0, 300.0],
    })
    outcomes_payments = pd.DataFrame({
        "outcome_id": pd.Series(dtype="object"),
        "data_pagamento": pd.Series(dtype="datetime64[ns]"),
        "valor_pago": pd.Series(dtype="float"),
    })

    caixa, _ = _run_caixa_block(
        _empty_incomes_with_date(), _empty_outcomes_with_date(),
        income_payments, outcomes_payments, incomes_active, outcomes_active,
    )

    jan = pd.Period("2025-01", freq="M")
    assert caixa[jan] == 1000.0
    assert len(caixa) == 1
