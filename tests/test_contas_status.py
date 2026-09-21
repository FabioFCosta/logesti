"""
Testa a lógica de status de `build_financial_view` em
`pages/04_Contas_A_Pagar.py` e `pages/03_Contas_A_Receber.py` (mudança
`saldo == 0` -> `saldo <= 0`, feita na tarefa pagar-a-mais-juros).

As páginas são scripts Streamlit com efeitos colaterais no nível do módulo
(autenticação Google, leitura da planilha) — importar o módulo inteiro
executaria isso. Em vez disso, extraímos só a função `build_financial_view`
via AST direto do arquivo fonte e a executamos isolada, sem duplicar a
lógica manualmente (o texto testado é exatamente o que está no arquivo).
"""
import ast
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_function(path, func_name):
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    func_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == func_name
    )
    func_source = ast.get_source_segment(source, func_node)
    namespace = {"pd": pd}
    exec(func_source, namespace)
    return namespace[func_name]


build_financial_view_pagar = _load_function(
    os.path.join(REPO_ROOT, "pages", "04_Contas_A_Pagar.py"), "build_financial_view"
)
build_financial_view_receber = _load_function(
    os.path.join(REPO_ROOT, "pages", "03_Contas_A_Receber.py"), "build_financial_view"
)


def _outcomes(rows):
    df = pd.DataFrame(rows)
    df["data_vencimento"] = pd.to_datetime(df["data_vencimento"])
    return df


def _out_payments(rows):
    return pd.DataFrame(rows, columns=["outcome_id", "valor_pago"])


def test_pagar_saldo_negativo_por_residuo_fica_pago():
    # excedente pago via fluxo novo quita a conta exatamente no saldo, mas
    # erro de ponto flutuante pode deixar um resíduo negativo tipo -1e-10
    outcomes = _outcomes([
        {"id": "o1", "valor": 100.0, "active": True, "data_vencimento": "2020-01-01"},
    ])
    payments = _out_payments([{"outcome_id": "o1", "valor_pago": 100.0000000001}])

    df = build_financial_view_pagar(outcomes, payments)

    assert df.loc[df["id"] == "o1", "status"].iloc[0] == "Pago"


def test_pagar_saldo_zero_exato_fica_pago():
    outcomes = _outcomes([
        {"id": "o1", "valor": 100.0, "active": True, "data_vencimento": "2020-01-01"},
    ])
    payments = _out_payments([{"outcome_id": "o1", "valor_pago": 100.0}])

    df = build_financial_view_pagar(outcomes, payments)

    assert df.loc[df["id"] == "o1", "status"].iloc[0] == "Pago"


def test_pagar_saldo_positivo_parcial_nao_fica_pago():
    outcomes = _outcomes([
        {"id": "o1", "valor": 100.0, "active": True, "data_vencimento": "2099-01-01"},
    ])
    payments = _out_payments([{"outcome_id": "o1", "valor_pago": 40.0}])

    df = build_financial_view_pagar(outcomes, payments)

    assert df.loc[df["id"] == "o1", "status"].iloc[0] == "Pago Parcial"


def test_pagar_sem_pagamento_vencido():
    outcomes = _outcomes([
        {"id": "o1", "valor": 100.0, "active": True, "data_vencimento": "2020-01-01"},
    ])
    payments = _out_payments([])

    df = build_financial_view_pagar(outcomes, payments)

    assert df.loc[df["id"] == "o1", "status"].iloc[0] == "Vencido"


def _incomes(rows):
    return pd.DataFrame(rows)


def _in_payments(rows):
    return pd.DataFrame(rows, columns=["income_id", "valor_pago"])


def test_receber_saldo_negativo_por_residuo_fica_recebido():
    incomes = _incomes([
        {"id": "i1", "valor": 100.0, "active": True},
    ])
    payments = _in_payments([{"income_id": "i1", "valor_pago": 100.0000000001}])

    df = build_financial_view_receber(incomes, payments)

    assert df.loc[df["id"] == "i1", "status"].iloc[0] == "Recebido"


def test_receber_saldo_zero_exato_fica_recebido():
    incomes = _incomes([
        {"id": "i1", "valor": 100.0, "active": True},
    ])
    payments = _in_payments([{"income_id": "i1", "valor_pago": 100.0}])

    df = build_financial_view_receber(incomes, payments)

    assert df.loc[df["id"] == "i1", "status"].iloc[0] == "Recebido"


def test_receber_saldo_positivo_parcial_nao_fica_recebido():
    incomes = _incomes([
        {"id": "i1", "valor": 100.0, "active": True},
    ])
    payments = _in_payments([{"income_id": "i1", "valor_pago": 40.0}])

    df = build_financial_view_receber(incomes, payments)

    assert df.loc[df["id"] == "i1", "status"].iloc[0] == "Recebido Parcialmente"


def test_receber_sem_pagamento_a_receber():
    incomes = _incomes([
        {"id": "i1", "valor": 100.0, "active": True},
    ])
    payments = _in_payments([])

    df = build_financial_view_receber(incomes, payments)

    assert df.loc[df["id"] == "i1", "status"].iloc[0] == "A Receber"
