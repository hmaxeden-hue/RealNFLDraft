from itertools import combinations, permutations

import numpy as np
import pandas as pd

from realdraft import history, optimizer
from realdraft.config import SLOT_MULTS


def brute_force(er, boost):
    best, arg = -1, None
    for combo in combinations(range(len(er)), 5):
        for perm in permutations(combo):
            v = sum(er[i] * (SLOT_MULTS[k] + boost[i]) for k, i in enumerate(perm))
            if v > best:
                best, arg = v, list(perm)
    return best, arg


def test_dp_matches_brute_force():
    rng = np.random.default_rng(1)
    for _ in range(25):
        n = 9
        er = rng.gamma(2, 1.2, n)
        boost = rng.choice([0, 0, 0.5, 1.1, 2.0, 3.0], n)
        lineup = optimizer.best_lineup(er, boost)
        best, _ = brute_force(er, boost)
        assert abs(optimizer.lineup_value(er, boost, lineup) - best) < 1e-9


def test_slot_order_is_by_expected_rating():
    er = np.array([1.0, 5.0, 3.0, 2.0, 4.0])
    boost = np.array([3.0, 0.0, 0.0, 3.0, 0.0])
    assert optimizer.best_lineup(er, boost) == [1, 4, 2, 3, 0]


def test_boosted_player_with_highest_rating_goes_to_slot_1():
    er = np.array([6.0, 5.0, 4.0, 3.0, 2.0, 1.0])
    boost = np.array([3.0, 0, 0, 0, 0, 0])
    assert optimizer.best_lineup(er, boost)[0] == 0


def test_formula_check_example_draft():
    # Draft vom 27.09.: App zeigt 18.44, additiv gerechnet 18.29 -> innerhalb Rundung.
    # (Dass additiv gilt, zeigt die App direkt: "Gesamt" 4.6x = 1.6 + 3.0.)
    picks = pd.DataFrame({"slot": [1, 2, 3, 4, 5], "boost": [0, 0, 3.0, 1.1, 3.0],
                          "rating": [2.1, 4.2, 0, 1.1, 0.9]})
    chk = history.formula_check(picks, 18.44)
    assert chk["berechnet"] == 18.29 and chk["ok"]
    assert not history.formula_check(picks, 20.0)["ok"]


def test_variants_contain_valid_lineups():
    rng = np.random.default_rng(2)
    n, N = 12, 500
    sims = rng.gamma(2, 1.0, (N, n))
    er, boost = sims.mean(0), rng.choice([0, 1.0, 3.0], n)
    v = optimizer.enumerate_variants(sims, er, boost, 10, 0.25, 0.95)
    for lineup, mean, qs, qu in v.values():
        assert len(set(lineup)) == 5 and qs <= mean <= qu
