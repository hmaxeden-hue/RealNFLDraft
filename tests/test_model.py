import numpy as np
import pandas as pd

from realdraft import optimizer, projection

PARAMS = {"groups": {"DB": {"slope": 0.2, "offset": 0.0, "noise": 0.0},
                     "WR": {"slope": 0.2, "offset": 0.0, "noise": 0.0}}}


def _df(rows):
    base = {"game_id": "g1", "team_spread": 0.0, "p_play": 1.0, "lam_int": 0.0, "lam_fr": 0.0}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_turnover_events_keep_expected_fp():
    df = _df([{"group": "DB", "team": "A", "opp": "B", "mu_fp": 8.0, "lam_int": 0.12, "lam_fr": 0.03}])
    sims, _ = projection.simulate(df, PARAMS, 20000)
    # E[Rating] = 0.2 · E[FP]; frühe Verletzungen (4 %, ~70 % Verlust) kosten knapp 3 %
    assert abs(sims[:, 0].mean() / (0.2 * 8.0) - 0.972) < 0.04
    # Turnover-Events erzeugen einen langen rechten Rand (INT = +2 Rating-Punkte)
    assert (sims[:, 0] > 3.5).mean() > 0.05


def test_scenario_masks_and_lineups():
    rows = [{"group": "WR", "team": t, "opp": o, "mu_fp": 10.0 + i} for i, (t, o) in
            enumerate([("A", "B")] * 4 + [("B", "A")] * 4)]
    df = _df(rows)
    sims, scen = projection.simulate(df, PARAMS, 5000)
    assert set(scen) == {"A", "B"} and 0.1 < scen["A"].mean() < 0.35
    er, boost = sims.mean(0), np.zeros(len(df))
    out = optimizer.scenario_lineups(sims, er, boost, scen)
    for s in out:
        assert len(set(s["lineup"])) == 5 and s["cond_mean"] > s["mean"]
