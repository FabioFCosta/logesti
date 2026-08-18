import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import reassign_quote_to_client


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
