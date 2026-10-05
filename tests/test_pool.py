import pandas as pd

from realdraft.pool import match_names

PLAYERS = pd.DataFrame({
    "player_id": ["a", "b", "c", "d"],
    "name": ["Josh Allen", "Josh Allen", "Kenneth Walker III", "Jaylen Waddle"],
    "team": ["BUF", "JAX", "KC", "DEN"], "position": ["QB", "DE", "RB", "WR"],
    "group": ["QB", "DL", "RB", "WR"], "pos_rank": [1, 1, 1, 1],
})


def test_abbreviated_names_and_suffix():
    e = pd.DataFrame({"name": ["K. Walker", "J. Waddle"], "boost": [0, 1.1]})
    out, problems = match_names(e, PLAYERS)
    assert list(out.player_id) == ["c", "d"] and not problems


def test_team_resolves_ambiguity():
    e = pd.DataFrame({"name": ["J. Allen"], "team": ["BUF"], "boost": [0]})
    out, problems = match_names(e, PLAYERS)
    assert out.player_id.iloc[0] == "a" and not problems


def test_ambiguity_is_reported():
    e = pd.DataFrame({"name": ["J. Allen"], "boost": [0]})
    _, problems = match_names(e, PLAYERS)
    assert problems and "mehrdeutig" in problems[0]


def test_page_data_has_no_nan():
    import json, math
    from realdraft import page
    d = page._clean({"a": float("nan"), "b": [1.0, float("inf"), {"c": "x"}]})
    assert d == {"a": None, "b": [1.0, None, {"c": "x"}]}
    json.dumps(d, allow_nan=False)
