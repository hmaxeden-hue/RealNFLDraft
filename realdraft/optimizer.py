"""Lineup-Optimierung.

Punkte = Σ Rating_i × (Slot_i + Boost_i). Der Boost hängt nicht vom Slot ab, also ist für
gegebene 5 Spieler die Reihenfolge nach erwartetem Rating optimal (Umordnungsungleichung).
Damit lässt sich die beste Auswahl exakt per dynamischer Programmierung finden: Spieler
nach E[Rating] sortieren, dann entscheidet man für jeden, ob er der k-te Pick wird.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

from .config import LINEUP_SIZE, SLOT_MULTS


def lineup_value(er, boost, idx) -> float:
    """Erwartete Punkte einer Auswahl, optimal sortiert."""
    idx = sorted(idx, key=lambda i: -er[i])
    return float(sum(er[i] * (SLOT_MULTS[k] + boost[i]) for k, i in enumerate(idx)))


def best_lineup(er, boost, exclude=()) -> list[int]:
    """Exakte Lösung: Indizes in Slot-Reihenfolge (Slot 1 zuerst)."""
    er, boost = np.asarray(er, float), np.asarray(boost, float)
    order = [i for i in np.argsort(-er, kind="stable") if i not in set(exclude)]
    K, n = LINEUP_SIZE, len(order)
    NEG = -1e18
    dp = np.full((n + 1, K + 1), NEG)
    dp[:, 0] = 0.0
    take = np.zeros((n + 1, K + 1), bool)
    for a in range(1, n + 1):
        i = order[a - 1]
        for k in range(1, K + 1):
            skip = dp[a - 1, k]
            pick = dp[a - 1, k - 1] + er[i] * (SLOT_MULTS[k - 1] + boost[i])
            if pick > skip:
                dp[a, k], take[a, k] = pick, True
            else:
                dp[a, k] = skip
    picks, k = [], K
    for a in range(n, 0, -1):
        if k and take[a, k]:
            picks.append(order[a - 1])
            k -= 1
    return picks[::-1]


def swap_alternatives(er, boost, lineup, n_alt=3) -> dict[int, list[tuple[int, float]]]:
    """Pro Lineup-Spieler: beste Ersatzspieler und Punkteverlust (Rest bleibt gleich)."""
    base = lineup_value(er, boost, lineup)
    others = [i for i in range(len(er)) if i not in lineup]
    out = {}
    for out_i in lineup:
        rest = [i for i in lineup if i != out_i]
        cands = sorted(((c, lineup_value(er, boost, rest + [c]) - base) for c in others),
                       key=lambda t: -t[1])
        out[out_i] = cands[:n_alt]
    return out


def enumerate_variants(sims, er, boost, pool_size, safe_q, upside_q, must_include=()):
    """Alle 5er-Kombinationen der besten Kandidaten simulieren.

    Rückgabe: dict variant -> (lineup in Slot-Reihenfolge, mean, q_safe, q_upside).
    Kandidaten = Top nach Einzelwert E[Rating] × (1.6 + Boost) plus must_include.
    """
    er, boost = np.asarray(er, float), np.asarray(boost, float)
    solo = er * (1.6 + boost)
    cand = list(dict.fromkeys(list(must_include) + list(np.argsort(-solo)[:pool_size])))
    combos = np.array(list(combinations(cand, LINEUP_SIZE)))
    # jede Kombination nach E[Rating] sortieren -> Slot-Reihenfolge
    order = np.argsort(-er[combos], axis=1, kind="stable")
    combos = np.take_along_axis(combos, order, axis=1)
    mults = np.asarray(SLOT_MULTS)[None, :] + boost[combos]

    best = {"mean": (None, -1e9), "safe": (None, -1e9), "upside": (None, -1e9)}
    stats = {}
    for start in range(0, len(combos), 400):
        c, m = combos[start:start + 400], mults[start:start + 400]
        scores = np.einsum("nck,ck->nc", sims[:, c], m)          # N x C
        mean = scores.mean(axis=0)
        qs = np.quantile(scores, [safe_q, upside_q], axis=0)
        for key, vals in (("mean", mean), ("safe", qs[0]), ("upside", qs[1])):
            j = int(np.argmax(vals))
            if vals[j] > best[key][1]:
                best[key] = (start + j, float(vals[j]))
        for j in range(len(c)):
            stats[start + j] = (mean[j], qs[0][j], qs[1][j])
    out = {}
    for key, (ci, _) in best.items():
        mean, qsafe, qup = stats[ci]
        out[key] = ([int(x) for x in combos[ci]], float(mean), float(qsafe), float(qup))
    return out


def score_distribution(sims, boost, lineup) -> np.ndarray:
    mults = np.asarray(SLOT_MULTS) + np.asarray(boost, float)[lineup]
    return sims[:, lineup] @ mults
