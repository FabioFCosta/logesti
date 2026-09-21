import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils
from utils import (
    reassign_quote_to_client,
    load_general_settings,
    load_type_options,
    save_type_option,
    set_type_option_active,
    save_km_rates,
)


def _incomes(rows):
    return pd.DataFrame(rows, columns=["id", "quote_id", "client_id", "valor"])


def _outcomes(rows):
    return pd.DataFrame(rows, columns=["id", "quote_id", "client_id", "valor"])


def test_reassign_moves_matching_rows_to_client():
    incomes = _incomes([
        {"id": "i1", "quote_id": "q1", "client_id": "", "valor": 100},
    ])
    outcomes = _outcomes([
        {"id": "o1", "quote_id": "q1", "client_id": "", "valor": 50},
    ])

    new_incomes, new_outcomes = reassign_quote_to_client(
        incomes, outcomes, quote_id="q1", client_id="q1")

    assert new_incomes.loc[0, "client_id"] == "q1"
    assert new_incomes.loc[0, "quote_id"] == ""
    assert new_outcomes.loc[0, "client_id"] == "q1"
    assert new_outcomes.loc[0, "quote_id"] == ""


def test_reassign_leaves_non_matching_rows_untouched():
    incomes = _incomes([
        {"id": "i1", "quote_id": "q1", "client_id": "", "valor": 100},
        {"id": "i2", "quote_id": "q2", "client_id": "c9", "valor": 200},
    ])
    outcomes = _outcomes([
        {"id": "o1", "quote_id": "q2", "client_id": "c9", "valor": 50},
    ])

    new_incomes, new_outcomes = reassign_quote_to_client(
        incomes, outcomes, quote_id="q1", client_id="q1")

    assert new_incomes.loc[1, "quote_id"] == "q2"
    assert new_incomes.loc[1, "client_id"] == "c9"
    assert new_outcomes.loc[0, "quote_id"] == "q2"
    assert new_outcomes.loc[0, "client_id"] == "c9"


def test_reassign_no_match_is_noop():
    incomes = _incomes([
        {"id": "i1", "quote_id": "q2", "client_id": "c9", "valor": 100},
    ])
    outcomes = _outcomes([
        {"id": "o1", "quote_id": "q2", "client_id": "c9", "valor": 50},
    ])

    new_incomes, new_outcomes = reassign_quote_to_client(
        incomes, outcomes, quote_id="q1", client_id="q1")

    pd.testing.assert_frame_equal(new_incomes, incomes)
    pd.testing.assert_frame_equal(new_outcomes, outcomes)


def test_reassign_moves_multiple_matching_rows():
    incomes = _incomes([
        {"id": "i1", "quote_id": "q1", "client_id": "", "valor": 100},
        {"id": "i2", "quote_id": "q1", "client_id": "", "valor": 300},
    ])
    outcomes = _outcomes([])

    new_incomes, _ = reassign_quote_to_client(
        incomes, outcomes, quote_id="q1", client_id="q1")

    assert (new_incomes["client_id"] == "q1").all()
    assert (new_incomes["quote_id"] == "").all()


def test_reassign_handles_completely_empty_dataframes():
    # load_incomes/load_outcomes retornam pd.DataFrame() sem coluna nenhuma
    # quando a aba correspondente não tem nenhuma linha (nem header) na planilha.
    incomes = pd.DataFrame()
    outcomes = _outcomes([
        {"id": "o1", "quote_id": "q1", "client_id": "", "valor": 50},
    ])

    new_incomes, new_outcomes = reassign_quote_to_client(
        incomes, outcomes, quote_id="q1", client_id="q1")

    assert new_incomes.empty
    assert new_outcomes.loc[0, "client_id"] == "q1"
    assert new_outcomes.loc[0, "quote_id"] == ""


def test_reassign_does_not_mutate_original_dataframes():
    incomes = _incomes([
        {"id": "i1", "quote_id": "q1", "client_id": "", "valor": 100},
    ])
    outcomes = _outcomes([
        {"id": "o1", "quote_id": "q1", "client_id": "", "valor": 50},
    ])

    reassign_quote_to_client(incomes, outcomes, quote_id="q1", client_id="q1")

    assert incomes.loc[0, "client_id"] == ""
    assert incomes.loc[0, "quote_id"] == "q1"
    assert outcomes.loc[0, "client_id"] == ""
    assert outcomes.loc[0, "quote_id"] == "q1"


# ---------------------------------------------------------------------------
# GENERAL_SETTINGS_DB: load_general_settings / load_type_options /
# save_type_option / set_type_option_active (tarefa settings-type-manager)
#
# Essas funções chamam a API do Sheets diretamente (get_sheets_service,
# ensure_sheet_exists, save_sheet). Pra testar a lógica pura sem rede,
# fazemos monkeypatch nesses três pontos de I/O e inspecionamos o que
# seria lido/gravado.
# ---------------------------------------------------------------------------

class _FakeValues:
    def __init__(self, result):
        self._result = result

    def get(self, spreadsheetId, range):
        return self

    def execute(self):
        return self._result


class _FakeSpreadsheets:
    def __init__(self, result):
        self._values = _FakeValues(result)

    def values(self):
        return self._values


class _FakeService:
    def __init__(self, result):
        self._spreadsheets = _FakeSpreadsheets(result)

    def spreadsheets(self):
        return self._spreadsheets


def _mock_sheet_read(monkeypatch, rows, headers=("key", "value", "type", "active")):
    """Faz load_general_settings enxergar `rows` como se viessem da planilha."""
    result = {"values": [list(headers)] + [list(r) for r in rows]} if rows else {"values": []}
    monkeypatch.setattr(utils, "get_sheets_service", lambda: _FakeService(result))


def _capture_save(monkeypatch):
    """Substitui save_sheet por uma função que só guarda o df recebido."""
    saved = {}

    def fake_save_sheet(file_id, sheet_name, df):
        saved["sheet_name"] = sheet_name
        saved["df"] = df.copy()

    monkeypatch.setattr(utils, "save_sheet", fake_save_sheet)
    monkeypatch.setattr(utils, "ensure_sheet_exists", lambda file_id, sheet_name: None)
    return saved


def test_load_general_settings_defaults_active_when_blank_or_missing(monkeypatch):
    _mock_sheet_read(monkeypatch, [
        ["Projeto", "", "income_options", ""],
        ["Visita", "", "outcomes_options", "false"],
        ["valor_km_carro", "1.2", "km", "TRUE"],
    ])

    settings = load_general_settings("file123")

    assert settings.loc[settings["key"] == "Projeto", "active"].iloc[0] == True
    assert settings.loc[settings["key"] == "Visita", "active"].iloc[0] == False
    assert settings.loc[settings["key"] == "valor_km_carro", "active"].iloc[0] == True


def test_load_general_settings_empty_sheet_returns_expected_columns(monkeypatch):
    _mock_sheet_read(monkeypatch, [])

    settings = load_general_settings("file123")

    assert list(settings.columns) == ["key", "value", "type", "active"]
    assert settings.empty


def test_load_type_options_seeds_defaults_when_category_absent(monkeypatch):
    _mock_sheet_read(monkeypatch, [])
    saved = _capture_save(monkeypatch)

    options = load_type_options("file123", "income_options")

    assert options[0] == "Reembolso"
    assert "Outros" in options
    # seed foi persistido na planilha
    seeded_df = saved["df"]
    assert (seeded_df["type"] == "income_options").sum() == len(options)
    assert seeded_df.loc[seeded_df["type"] == "income_options", "active"].all()


def test_load_type_options_returns_only_active_rows_for_category(monkeypatch):
    _mock_sheet_read(monkeypatch, [
        ["Projeto", "", "income_options", "TRUE"],
        ["Reembolso", "", "income_options", "false"],
        ["Visita", "", "outcomes_options", "TRUE"],
    ])

    options = load_type_options("file123", "income_options")

    assert options == ["Projeto"]


def test_save_type_option_reactivates_instead_of_duplicating(monkeypatch):
    _mock_sheet_read(monkeypatch, [
        ["Reembolso", "", "income_options", "false"],
        ["Projeto", "", "income_options", "TRUE"],
    ])
    saved = _capture_save(monkeypatch)

    save_type_option("file123", "income_options", "Reembolso")

    df = saved["df"]
    matches = df[(df["key"] == "Reembolso") & (df["type"] == "income_options")]
    assert len(matches) == 1
    assert matches.iloc[0]["active"] == True


def test_save_type_option_adds_new_row_when_absent(monkeypatch):
    _mock_sheet_read(monkeypatch, [
        ["Projeto", "", "income_options", "TRUE"],
    ])
    saved = _capture_save(monkeypatch)

    save_type_option("file123", "income_options", "Nova Opcao")

    df = saved["df"]
    matches = df[(df["key"] == "Nova Opcao") & (df["type"] == "income_options")]
    assert len(matches) == 1
    assert matches.iloc[0]["active"] == True
    assert len(df) == 2


def test_save_type_option_same_key_different_category_not_confused(monkeypatch):
    # "Reembolso" existe em income_options ativo; adicionar em outcomes_options
    # não deve reativar/duplicar a linha errada.
    _mock_sheet_read(monkeypatch, [
        ["Reembolso", "", "income_options", "TRUE"],
    ])
    saved = _capture_save(monkeypatch)

    save_type_option("file123", "outcomes_options", "Reembolso")

    df = saved["df"]
    assert len(df) == 2
    income_row = df[(df["key"] == "Reembolso") & (df["type"] == "income_options")]
    outcome_row = df[(df["key"] == "Reembolso") & (df["type"] == "outcomes_options")]
    assert len(income_row) == 1 and len(outcome_row) == 1
    assert outcome_row.iloc[0]["active"] == True


def test_set_type_option_active_deactivates_only_matching_row(monkeypatch):
    _mock_sheet_read(monkeypatch, [
        ["Projeto", "", "income_options", "TRUE"],
        ["Reembolso", "", "income_options", "TRUE"],
        ["Projeto", "", "outcomes_options", "TRUE"],
    ])
    saved = _capture_save(monkeypatch)

    set_type_option_active("file123", "income_options", "Projeto", False)

    df = saved["df"]
    assert df.loc[(df["key"] == "Projeto") & (df["type"] == "income_options"), "active"].iloc[0] == False
    assert df.loc[(df["key"] == "Reembolso") & (df["type"] == "income_options"), "active"].iloc[0] == True
    # linha de outra categoria com o mesmo nome não é afetada
    assert df.loc[(df["key"] == "Projeto") & (df["type"] == "outcomes_options"), "active"].iloc[0] == True


def test_set_type_option_active_reactivates_matching_row(monkeypatch):
    _mock_sheet_read(monkeypatch, [
        ["Visita", "", "outcomes_options", "false"],
    ])
    saved = _capture_save(monkeypatch)

    set_type_option_active("file123", "outcomes_options", "Visita", True)

    df = saved["df"]
    assert df.loc[(df["key"] == "Visita") & (df["type"] == "outcomes_options"), "active"].iloc[0] == True


def test_save_km_rates_preserves_other_rows_instead_of_overwriting_sheet(monkeypatch):
    # Regressao critica: versao antiga de save_km_rates recriava a aba
    # inteira so com as 2 linhas de km, apagando as linhas de
    # income_options/outcomes_options. A versao corrigida faz
    # load-modify-save.
    _mock_sheet_read(monkeypatch, [
        ["valor_km_carro", "1.0", "km", "TRUE"],
        ["valor_km_moto", "0.5", "km", "TRUE"],
        ["Projeto", "", "income_options", "TRUE"],
        ["Visita", "", "outcomes_options", "TRUE"],
    ])
    saved = _capture_save(monkeypatch)

    save_km_rates("file123", {"valor_km_carro": 2.5, "valor_km_moto": 1.1})

    df = saved["df"]
    assert len(df) == 4
    assert df.loc[df["key"] == "valor_km_carro", "value"].iloc[0] == 2.5
    assert df.loc[df["key"] == "valor_km_moto", "value"].iloc[0] == 1.1
    assert (df[df["type"] == "income_options"]["key"] == "Projeto").any()
    assert (df[df["type"] == "outcomes_options"]["key"] == "Visita").any()


def test_save_km_rates_creates_rows_when_absent(monkeypatch):
    _mock_sheet_read(monkeypatch, [
        ["Projeto", "", "income_options", "TRUE"],
    ])
    saved = _capture_save(monkeypatch)

    save_km_rates("file123", {"valor_km_carro": 3.0, "valor_km_moto": 1.5})

    df = saved["df"]
    assert len(df) == 3
    assert df.loc[df["key"] == "valor_km_carro", "value"].iloc[0] == 3.0
    assert df.loc[df["key"] == "valor_km_moto", "value"].iloc[0] == 1.5
    assert (df[df["type"] == "income_options"]["key"] == "Projeto").any()
