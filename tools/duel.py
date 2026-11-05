"""Wochenduell gegen einen Freund: Lineup, das P(eigener Score − Score des Freundes > Rückstand) maximiert.

Aufruf: python tools/duel.py <datum> --rueckstand 10 --freund "JSN,?,Sam Darnold,?,Tory Taylor"
'?' = unbekannter Slot; dafür werden plausible Offensivspieler eingesetzt und gemittelt.
Gemeinsame Spieler auf gleichem Slot heben sich auf; wer zurückliegt, braucht Streuung im Abstand.
"""
import argparse, itertools
import numpy as np
from realdraft import config, features, pool, projection


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date"); ap.add_argument("--rueckstand", type=float, default=0.0)
    ap.add_argument("--freund", required=True, help="5 Namen in Slot-Reihenfolge, '?' für unbekannt")
    ap.add_argument("--sims", type=int, default=40000)
    a = ap.parse_args()
    sl = features.slate(a.date); pl = features.slate_players(sl)
    bo, _ = pool.load_pool(a.date, pl); ov, _ = pool.load_overrides(a.date, pl)
    df, sims, _ = projection.project(a.date, bo, ov, n_sims=a.sims)
    df = df.reset_index(drop=True); name = df.name.tolist(); idx = {n: i for i, n in enumerate(name)}
    b, S = df.boost.to_numpy(), config.SLOT_MULTS

    def score(lu):
        return sum(sims[:, i] * (S[k] + b[i]) for k, i in enumerate(lu))

    friend = [s.strip() for s in a.freund.split(",")]
    known = [n for n in friend if n != "?"]
    holes = [k for k, n in enumerate(friend) if n == "?"]
    off = df[df.group.isin(["QB", "RB", "WR", "TE"]) & (df.er > 0.8) & ~df.name.isin(known)]
    fill = off.assign(v=off.er * (1.6 + off.boost)).sort_values("v", ascending=False).name.head(8).tolist()
    lineups = []
    for combo in itertools.permutations(fill, len(holes)):
        f = list(friend)
        for k, n in zip(holes, combo):
            f[k] = n
        lineups.append([idx[n] for n in f])
    lineups = sorted(lineups, key=lambda lu: -score(lu).mean())[:12]
    FS = np.stack([score(lu) for lu in lineups])

    def obj(lu):
        return float((score(lu)[None, :] - FS > a.rueckstand).mean())

    df["v"] = df.er * (1.2 + df.boost)
    df["hi"] = np.quantile(sims, 0.9, axis=0) * (1.2 + df.boost)
    cand = sorted(set(df.nlargest(28, "v").index) | set(df.nlargest(20, "hi").index))
    model = list(df.nlargest(5, "v").index)
    rng = np.random.default_rng(1)
    best = (obj(model), model)
    for st in [model] + [list(rng.choice(cand, 5, replace=False)) for _ in range(12)]:
        cur, cv, improved = list(st), obj(st), True
        while improved:
            improved = False
            for k in range(5):
                for c in cand:
                    if c in cur:
                        continue
                    t = cur.copy(); t[k] = c
                    if (v := obj(t)) > cv + 1e-4:
                        cur, cv, improved = t, v, True
            for i, j in itertools.combinations(range(5), 2):
                t = cur.copy(); t[i], t[j] = t[j], t[i]
                if (v := obj(t)) > cv + 1e-4:
                    cur, cv, improved = t, v, True
        if cv > best[0]:
            best = (cv, cur)
    p, lu = best
    print(f"Bestes Duell-Lineup: P(Abstand > {a.rueckstand:g}) = {p:.1%}, E = {score(lu).mean():.1f}")
    for k, i in enumerate(lu):
        print(f"  {k + 1}. {name[i]} ({df.team[i]}, +{b[i]:.1f}, {S[k] + b[i]:.1f}x)")


if __name__ == "__main__":
    main()
