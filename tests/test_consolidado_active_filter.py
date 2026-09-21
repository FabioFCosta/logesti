"""
Testa `_filter_active` em `Consolidado.py` (tarefa
fix-consolidado-caixa-e-futuros): a coluna `active` vem da Sheets API como
string ("TRUE"/"FALSE"), não bool -- comparar com `!= False` nunca filtra
nada. `_filter_active` corrige isso com `.astype(str).str.upper() != "FALSE"`.

`Consolidado.py` é um script Streamlit com efeitos colaterais no nível do
módulo (autenticação Google, leitura da planilha) -- importar o módulo
inteiro executaria isso. Em vez disso, extraímos só a função `_filter_active`
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


_filter_active = _load_function(
    os.path.join(REPO_ROOT, "Consolidado.py"), "_filter_active"
)


def test_filter_active_string_true_false_from_sheets():
    df = pd.DataFrame({
        "id": ["a", "b"],
        "active": ["TRUE", "FALSE"],
    })

    result = _filter_active(df)

    assert list(result["id"]) == ["a"]


def test_filter_active_lowercase_string_values():
    df = pd.DataFrame({
        "id": ["a", "b"],
        "active": ["true", "false"],
    })

    result = _filter_active(df)

    assert list(result["id"]) == ["a"]


def test_filter_active_real_bool_values_still_work():
    df = pd.DataFrame({
        "id": ["a", "b"],
        "active": [True, False],
    })

    result = _filter_active(df)

    assert list(result["id"]) == ["a"]


def test_filter_active_no_active_column_returns_unchanged():
    df = pd.DataFrame({"id": ["a", "b"]})

    result = _filter_active(df)

    assert list(result["id"]) == ["a", "b"]


def test_filter_active_empty_dataframe():
    df = pd.DataFrame({"id": [], "active": []})

    result = _filter_active(df)

    assert result.empty
