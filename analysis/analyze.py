#!/usr/bin/env python3
"""
Statistical analysis of an experiment folder produced by scripts/run_experiment.sh.

Design (per scenario, "fixo" and "variavel"):
  * block     = (instance, size): every algorithm runs on the SAME instance, so values are paired
  * treatment = algorithm (GR, GRF, GCB, WF, SAGR, SAGRF, SAGCB, SAWF)
  * response  = penalty (Total_cost / Max_cost, in %), averaged over the runs of the block
                (GCB and WF are deterministic: one value per block)
  * Friedman test (all algorithms) -> Nemenyi post-hoc + critical-difference diagram
  * Wilcoxon signed-rank test on all pairs, Holm correction (family = 28 pairs per scenario)
  * effect sizes: Kendall's W (Friedman), rank-biserial correlation (Wilcoxon)

Usage: python analysis/analyze.py RESULTS_DIR [--out DIR]
"""
import argparse
import glob
import itertools
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy import stats
from statsmodels.stats.multitest import multipletests

ALGS = ["GR", "GRF", "GCB", "WF", "SAGR", "SAGRF", "SAGCB", "SAWF"]
HEUR = {"GREEDY_RANDOM": "GR", "GREEDY_RANDOM_FALLBACK": "GRF", "GREEDY_CB": "GCB", "GREEDY_WF": "WF"}
SA_INIT = {"GREEDY_RANDOM": "SAGR", "GREEDY_RANDOM_FALLBACK": "SAGRF", "GREEDY_CB": "SAGCB", "GREEDY_WF": "SAWF"}
SCEN = ["fixo", "variavel"]
SCEN_PT = {"fixo": "custo fixo", "variavel": "custo variável"}
ALPHA = 0.05


# ----------------------------------------------------------------------------- data
def load(root):
    frames = []
    for path in glob.glob(os.path.join(root, "inst_*", "*", "results", "*", "*.txt")):
        if "drawing" in path:
            continue
        parts = path.split(os.sep)
        df = pd.read_csv(path, sep=";")
        df["alg"] = df["Initial_Heuristic"].map(SA_INIT) if "Initial_Heuristic" in df.columns else df["Algorithm"].map(HEUR)
        df["inst"] = int(parts[-5].split("_")[1])
        df["scen"] = parts[-4]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True).dropna(subset=["alg"])
    df["pen"] = 100.0 * df["Total_cost"] / df["Max_cost"]
    df["acc"] = 100.0 * df["Devices_served"] / df["Devices"]
    df = df.rename(columns={"Devices": "size", "Execution_time": "time"})
    return df[["scen", "inst", "size", "alg", "Run", "pen", "acc", "time"]]


def blocks(df, scen, col="pen"):
    """Wide matrix (rows = blocks, columns = algorithms) of block means."""
    b = df[df.scen == scen].groupby(["inst", "size", "alg"])[col].mean().unstack("alg")
    return b[ALGS].dropna()


# ----------------------------------------------------------------------------- statistics
def rank_biserial(a, b):
    """Matched-pairs rank-biserial correlation; > 0 means a tends to be larger (worse) than b."""
    d = np.asarray(a) - np.asarray(b)
    d = d[d != 0]
    if len(d) == 0:
        return 0.0
    r = stats.rankdata(np.abs(d))
    wp, wm = r[d > 0].sum(), r[d < 0].sum()
    return float((wp - wm) / (wp + wm))


def wilcoxon_p(a, b):
    d = np.asarray(a) - np.asarray(b)
    if not np.any(d != 0):
        return 1.0
    try:
        return float(stats.wilcoxon(a, b, zero_method="wilcox").pvalue)
    except ValueError:
        return 1.0


def friedman(M):
    n, k = M.shape
    stat, p = stats.friedmanchisquare(*[M[:, j] for j in range(k)])
    return float(stat), float(p), float(stat / (n * (k - 1)))


def pairwise(M):
    rows = []
    for i, j in itertools.combinations(range(M.shape[1]), 2):
        a, b = M[:, i], M[:, j]
        d = a - b
        rows.append(dict(A=ALGS[i], B=ALGS[j], n=len(d), n_nao_nulos=int((d != 0).sum()),
                         mediana_A_menos_B=float(np.median(d)), media_A_menos_B=float(d.mean()),
                         r_rb=rank_biserial(a, b), p=wilcoxon_p(a, b)))
    df = pd.DataFrame(rows)
    df["p_holm"] = multipletests(df["p"], alpha=ALPHA, method="holm")[1]
    df["significativo"] = df["p_holm"] < ALPHA
    return df


def pair_row(pw, a, b):
    """Row for the ordered pair (a, b): sign-adjusted so 'mediana' = median(a - b)."""
    r = pw[((pw.A == a) & (pw.B == b)) | ((pw.A == b) & (pw.B == a))].iloc[0].copy()
    if r.A != a:
        r["mediana_A_menos_B"] = -r["mediana_A_menos_B"]
        r["media_A_menos_B"] = -r["media_A_menos_B"]
        r["r_rb"] = -r["r_rb"]
    return r


def sentence(pw, a, b):
    r = pair_row(pw, a, b)
    if not r["significativo"]:
        return (f"**{a} x {b}**: sem diferença significativa (p_Holm = {r['p_holm']:.3g}; "
                f"diferença mediana {r['mediana_A_menos_B']:+.2f} p.p.).")
    # direction comes from the Wilcoxon effect (r_rb < 0: a tends to have the smaller penalty), not from the median,
    # which can be exactly 0 when many blocks tie (small sizes)
    melhor, pior = (a, b) if r["r_rb"] < 0 else (b, a)
    nota = " Mediana ≈ 0 por empates nos tamanhos pequenos; veja as médias por tamanho." if abs(r["mediana_A_menos_B"]) < 0.05 else ""
    return (f"**{melhor} é melhor que {pior}** (p_Holm = {r['p_holm']:.3g}; diferença média "
            f"{abs(r['media_A_menos_B']):.2f} p.p. e mediana {abs(r['mediana_A_menos_B']):.2f} p.p. de penalidade; "
            f"efeito rank-biserial {abs(r['r_rb']):.2f}).{nota}")


# ----------------------------------------------------------------------------- plots
def cd_diagram(avg, cd, title, path):
    k = len(ALGS)
    order = np.argsort(avg)
    r = avg[order]
    cliques, last_j = [], -1
    for i in range(k):
        j = max(t for t in range(i, k) if r[t] - r[i] < cd)
        if j > i and j > last_j:
            cliques.append((r[i], r[j]))
            last_j = j
    half = (k + 1) // 2
    top = 0.9
    bar0 = top - 0.07
    y0 = bar0 - 0.05 * len(cliques) - 0.07
    ymin = y0 - 0.085 * (half - 1) - 0.08
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.set_xlim(-1.6, k + 2.6)
    ax.set_ylim(ymin, 1.15)
    ax.axis("off")
    ax.plot([1, k], [top, top], "k", lw=1)
    for t in range(1, k + 1):
        ax.plot([t, t], [top, top + 0.03], "k", lw=1)
        ax.text(t, top + 0.06, str(t), ha="center", va="bottom", fontsize=9)
    ax.plot([1, 1 + cd], [1.1, 1.1], "k", lw=2)
    ax.text(1 + cd / 2, 1.12, f"CD = {cd:.2f}", ha="center", va="bottom", fontsize=9)
    for n, (lo, hi) in enumerate(cliques):
        y = bar0 - 0.05 * n
        ax.plot([lo - 0.03, hi + 0.03], [y, y], "k", lw=3, solid_capstyle="butt")
    for idx, a in enumerate(order):
        x, y = avg[a], y0 - 0.085 * (idx if idx < half else idx - half)
        ax.plot([x, x], [top, y], "k", lw=0.8)
        if idx < half:
            ax.plot([x, 0.7], [y, y], "k", lw=0.8)
            ax.text(0.65, y, f"{ALGS[a]} ({x:.2f})", ha="right", va="center", fontsize=9)
        else:
            ax.plot([x, k + 0.3], [y, y], "k", lw=0.8)
            ax.text(k + 0.35, y, f"({x:.2f}) {ALGS[a]}", ha="left", va="center", fontsize=9)
    ax.set_title(title + "\nbarras grossas ligam algoritmos que Nemenyi não distingue", fontsize=10)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def wtl(M, tol=1e-9):
    """Win/tie/loss counts of row vs column over the blocks (win = smaller penalty)."""
    n, k = M.shape
    W = np.zeros((k, k), int)
    D = np.zeros((k, k), int)
    for i in range(k):
        for j in range(k):
            if i != j:
                d = M[:, i] - M[:, j]
                W[i, j] = int((d < -tol).sum())
                D[i, j] = int((d > tol).sum())
    T = n - W - D
    np.fill_diagonal(T, 0)
    return W, T, D


def sig_lookup(pw):
    out = {}
    for r in pw.itertuples():
        out[(r.A, r.B)] = out[(r.B, r.A)] = bool(r.significativo)
    return out


def plot_wtl(mats, pws, out):
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    k = len(ALGS)
    for ax, scen in zip(axes, SCEN):
        M = mats[scen]
        W, T, D = wtl(M)
        sig = sig_lookup(pws[scen])
        score = (W - D) / M.shape[0]
        im = ax.imshow(score, cmap="RdBu", vmin=-1, vmax=1)
        for i in range(k):
            for j in range(k):
                if i != j:
                    txt = f"{W[i, j]}-{T[i, j]}-{D[i, j]}" + ("*" if sig[(ALGS[i], ALGS[j])] else "")
                    ax.text(j, i, txt, ha="center", va="center", fontsize=8, color="white" if abs(score[i, j]) > 0.6 else "black")
        ax.set_xticks(range(k)); ax.set_xticklabels(ALGS, rotation=45)
        ax.set_yticks(range(k)); ax.set_yticklabels(ALGS)
        ax.set_title(f"{SCEN_PT[scen]}: linha contra coluna, V-E-D em {M.shape[0]} blocos\n* = significativo no Wilcoxon + Holm", fontsize=10)
    fig.colorbar(im, ax=axes, shrink=0.8, label="(vitórias − derrotas) / blocos; azul = a linha ganha")
    fig.savefig(os.path.join(out, "fig_vitorias.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_penalty(desc, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    cmap = plt.get_cmap("tab10")
    for ax, scen in zip(axes, SCEN):
        for n, a in enumerate(ALGS):
            d = desc[(desc.scen == scen) & (desc.alg == a)].sort_values("size")
            ax.errorbar(d["size"], d["pen_media"], yerr=d["pen_ic95"], color=cmap(n), marker="o", ms=4, lw=1.5,
                        ls="-" if a.startswith("SA") else "--", capsize=2, label=a)
        ax.set_title(SCEN_PT[scen]); ax.set_xlabel("dispositivos"); ax.grid(alpha=0.3)
    axes[0].set_ylabel("penalidade (% do máximo)")
    axes[1].legend(ncol=2, fontsize=8)
    fig.savefig(os.path.join(out, "fig_penalidade_por_tamanho.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_delta(df, out):
    """Paired difference to GCB per size (mean over instances, 95% CI); negative = better than GCB."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    cmap = plt.get_cmap("tab10")
    for ax, scen in zip(axes, SCEN):
        P = blocks(df, scen, "pen")
        for a in ["WF", "SAGR", "SAGRF", "SAGCB", "SAWF"]:
            xs, ys, es = [], [], []
            for size in sorted(P.index.get_level_values("size").unique()):
                d = (P[P.index.get_level_values("size") == size][a] - P[P.index.get_level_values("size") == size]["GCB"]).values
                xs.append(int(size)); ys.append(d.mean())
                es.append(stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d)))
            n = ALGS.index(a)
            ax.errorbar(xs, ys, yerr=es, color=cmap(n), marker="o", ms=4, lw=1.5, capsize=2,
                        ls="-" if a.startswith("SA") else "--", label=a)
        ax.axhline(0, color="k", lw=1)
        ax.set_title(SCEN_PT[scen]); ax.set_xlabel("dispositivos"); ax.grid(alpha=0.3)
    axes[0].set_ylabel("penalidade − GCB (p.p.)\nabaixo de 0 = melhor que a GCB")
    axes[1].legend(ncol=2, fontsize=8)
    fig.savefig(os.path.join(out, "fig_diferenca_vs_gcb.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_time(df, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    big = df["size"].max()
    for ax, scen in zip(axes, SCEN):
        d = df[(df.scen == scen) & (df["size"] == big)]
        ax.boxplot([d[d.alg == a]["time"].values for a in ALGS], showfliers=False)
        ax.set_xticks(range(1, len(ALGS) + 1))
        ax.set_xticklabels(ALGS)
        ax.axhline(1.0, color="red", lw=1)
        ax.set_yscale("log"); ax.set_title(f"{SCEN_PT[scen]}, {big} dispositivos"); ax.grid(alpha=0.3, which="both")
        ax.tick_params(axis="x", rotation=45)
    axes[0].set_ylabel("tempo de execução (s), linha vermelha = 1 s")
    fig.savefig(os.path.join(out, "fig_tempo.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------------------- report helpers
def fmt(v):
    if isinstance(v, (bool, np.bool_)):
        return "sim" if v else "não"
    if isinstance(v, (float, np.floating)):
        return f"{v:.3g}" if abs(v) < 1000 else f"{v:.0f}"
    return str(v)


def md(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or os.path.join(args.root, "analysis")
    os.makedirs(out, exist_ok=True)

    df = load(args.root)
    n_inst = df["inst"].nunique()
    sizes = [int(s) for s in sorted(df["size"].unique())]
    desc_rows, fr, pws, cds, ranks_tbl = [], {}, {}, {}, {}
    mats = {}
    time_rows = []

    for scen in SCEN:
        P = blocks(df, scen, "pen")
        M = P.values
        n, k = M.shape
        fr[scen] = friedman(M) + (n,)
        ranks = np.apply_along_axis(stats.rankdata, 1, M)
        avg = ranks.mean(axis=0)
        ranks_tbl[scen] = dict(zip(ALGS, avg))
        cds[scen] = float(stats.studentized_range.ppf(1 - ALPHA, k, np.inf) / np.sqrt(2) * np.sqrt(k * (k + 1) / (6.0 * n)))
        pws[scen] = pairwise(M)
        mats[scen] = M
        pws[scen].to_csv(os.path.join(out, f"wilcoxon_holm_{scen}.csv"), index=False)
        nem = sp.posthoc_nemenyi_friedman(P[ALGS])
        nem.to_csv(os.path.join(out, f"nemenyi_p_{scen}.csv"))
        cd_diagram(avg, cds[scen], f"Diagrama de diferença crítica (Nemenyi, α = 0,05), {SCEN_PT[scen]}, {n} blocos",
                   os.path.join(out, f"fig_cd_{scen}.png"))
        A = blocks(df, scen, "acc")
        T = blocks(df, scen, "time")
        for size in sizes:
            for a in ALGS:
                v = P[P.index.get_level_values("size") == size][a].values
                m = len(v)
                ic = stats.t.ppf(0.975, m - 1) * v.std(ddof=1) / np.sqrt(m) if m > 1 else np.nan
                desc_rows.append(dict(scen=scen, size=size, alg=a, n_inst=m, pen_media=v.mean(), pen_ic95=ic,
                                      aceitacao=A[A.index.get_level_values("size") == size][a].mean(),
                                      tempo_s=T[T.index.get_level_values("size") == size][a].mean()))
        for a in ALGS:
            t = df[(df.scen == scen) & (df.alg == a)]["time"]
            time_rows.append(dict(cenario=scen, alg=a, mediana_s=t.median(), p95_s=t.quantile(0.95), max_s=t.max(),
                                  acima_de_1s=int((t > 1.0).sum()), execucoes=len(t)))
    desc = pd.DataFrame(desc_rows)
    desc.to_csv(os.path.join(out, "descritivo.csv"), index=False)
    tdf = pd.DataFrame(time_rows)
    tdf.to_csv(os.path.join(out, "tempo.csv"), index=False)
    plot_penalty(desc, out)
    plot_wtl(mats, pws, out)
    plot_delta(df, out)
    plot_time(df, out)

    # per-size tests for the two key pairs (Holm over scenario x size)
    key_pairs = [("WF", "GCB"), ("SAWF", "SAGRF")]
    per_size = []
    for scen in SCEN:
        P = blocks(df, scen, "pen")
        for size in sizes:
            sub = P[P.index.get_level_values("size") == size]
            for a, b in key_pairs:
                per_size.append(dict(par=f"{a} x {b}", cenario=scen, tamanho=size, n=len(sub),
                                     mediana_A_menos_B=float(np.median(sub[a] - sub[b])),
                                     r_rb=rank_biserial(sub[a], sub[b]), p=wilcoxon_p(sub[a], sub[b])))
    ps = pd.DataFrame(per_size)
    ps["p_holm"] = np.nan
    for par in ps["par"].unique():
        m = ps["par"] == par
        ps.loc[m, "p_holm"] = multipletests(ps.loc[m, "p"], alpha=ALPHA, method="holm")[1]
    ps.to_csv(os.path.join(out, "por_tamanho.csv"), index=False)

    # robustness: one block per instance (mean over sizes), because the sizes of one instance share services/servers.
    # With n = 10 the smallest two-sided Wilcoxon p is 2/2^10, so Holm is applied only to 4 planned pairs.
    planned = [("WF", "GCB"), ("SAWF", "SAGR"), ("SAWF", "SAGRF"), ("SAWF", "SAGCB")]
    rob_fr, rob_rows = {}, []
    for scen in SCEN:
        Pi = blocks(df, scen, "pen").groupby("inst").mean()[ALGS]
        rob_fr[scen] = friedman(Pi.values) + (len(Pi),)
        rows = [dict(cenario=scen, par=f"{a} x {b}", n=len(Pi), A_menor_em=int((Pi[a] < Pi[b]).sum()),
                     mediana_A_menos_B=float(np.median(Pi[a] - Pi[b])), r_rb=rank_biserial(Pi[a], Pi[b]),
                     p=wilcoxon_p(Pi[a], Pi[b])) for a, b in planned]
        r = pd.DataFrame(rows)
        r["p_holm"] = multipletests(r["p"], alpha=ALPHA, method="holm")[1]
        rob_rows.append(r)
    rob = pd.concat(rob_rows, ignore_index=True)
    rob.to_csv(os.path.join(out, "robustez_por_instancia.csv"), index=False)

    # ------------------------------------------------------------------ report
    L = ["# Relatório estatístico\n",
         f"Pasta analisada: `{args.root}`. {n_inst} instâncias, tamanhos {sizes}, α do teste = {ALPHA}. "
         "Penalidade = custo dos não atendidos / custo máximo (%), menor é melhor. "
         "Blocos = (instância, tamanho); cada bloco usa a média das execuções.\n",
         "## Respostas diretas\n"]
    L.append("**1. Existe diferença entre os 8 algoritmos? (Friedman)**\n")
    for s in SCEN:
        st_, p_, w_, n_ = fr[s]
        L.append(f"- {SCEN_PT[s]}: χ² = {st_:.1f}, p = {p_:.3g}, W de Kendall = {w_:.2f} ({n_} blocos). "
                 + ("Há diferença significativa entre os algoritmos." if p_ < ALPHA else "Sem evidência de diferença."))
    L.append("\n**2. A WF é melhor que a GCB? E o SA a partir da WF é o melhor SA? (Wilcoxon pareado + Holm, 28 pares por cenário)**\n")
    for s in SCEN:
        L.append(f"- {SCEN_PT[s]}: {sentence(pws[s], 'WF', 'GCB')}")
        for other in ["SAGR", "SAGRF", "SAGCB"]:
            L.append(f"  - {sentence(pws[s], 'SAWF', other)}")
    L.append("\n**3. O resultado muda entre os cenários?** Compare os itens acima e as tabelas por tamanho abaixo.\n")
    L.append("## Ranks médios (Friedman; 1 = menor penalidade)\n")
    L.append(md(pd.DataFrame({s: ranks_tbl[s] for s in SCEN}).reset_index().rename(columns={"index": "algoritmo"}).sort_values("fixo")))
    L.append("\nDiferença crítica de Nemenyi: " + ", ".join(f"{SCEN_PT[s]} = {cds[s]:.2f}" for s in SCEN)
             + ". Algoritmos com ranks médios mais próximos que isso não diferem pelo Nemenyi. Figuras: `fig_cd_fixo.png`, `fig_cd_variavel.png`.\n")
    for s in SCEN:
        L.append(f"## Wilcoxon + Holm, {SCEN_PT[s]} (28 pares; `wilcoxon_holm_{s}.csv`)\n")
        pw = pws[s]
        L.append(md(pw.sort_values("p_holm").head(12).drop(columns=["n"])))
        L.append(f"\n{int(pw.significativo.sum())} de {len(pw)} pares significativos. Mostrados os 12 de menor p ajustado.\n")
    L.append("## Matriz de vitórias, empates e derrotas (V-E-D)\n")
    L.append("Cada célula compara o algoritmo da **linha** com o da **coluna** nos blocos (instância, tamanho): "
             "V = blocos em que a linha teve penalidade menor, E = iguais, D = maiores. `*` marca os pares significativos no "
             "Wilcoxon + Holm. É um resumo descritivo; a conclusão estatística continua sendo a do Wilcoxon + Holm. "
             "Figura: `fig_vitorias.png`.\n")
    for s_ in SCEN:
        M_ = mats[s_]
        W_, T_, D_ = wtl(M_)
        sg = sig_lookup(pws[s_])
        tab = pd.DataFrame([[("-" if i == j else f"{W_[i, j]}-{T_[i, j]}-{D_[i, j]}" + ("*" if sg[(ALGS[i], ALGS[j])] else ""))
                             for j in range(len(ALGS))] for i in range(len(ALGS))], columns=ALGS)
        tab.insert(0, "linha", ALGS)
        L.append(f"### {SCEN_PT[s_]}\n")
        L.append(md(tab))
        saldo = pd.DataFrame({"algoritmo": ALGS, "vitórias": W_.sum(axis=1), "derrotas": D_.sum(axis=1)})
        saldo["saldo"] = saldo["vitórias"] - saldo["derrotas"]
        L.append("\n" + md(saldo.sort_values("saldo", ascending=False)))
        agree = sum(1 for r in pws[s_].itertuples() if r.significativo and
                    ((W_[ALGS.index(r.A), ALGS.index(r.B)] > D_[ALGS.index(r.A), ALGS.index(r.B)]) == (r.r_rb < 0)))
        n_sig = int(pws[s_].significativo.sum())
        L.append(f"\nConferência: dos {n_sig} pares significativos no Wilcoxon + Holm, {agree} têm saldo de vitórias na mesma direção.\n")
    L.append("## Pares-chave por tamanho (Holm sobre cenário x tamanho)\n")
    L.append(md(ps))
    L.append("\n## Robustez: um bloco por instância (média dos tamanhos)\n")
    L.append("Os tamanhos de uma mesma instância compartilham serviços e servidores, então os blocos (instância, tamanho) "
             "não são totalmente independentes. Aqui cada instância vale um bloco (n = " + str(n_inst) + "). "
             "`A_menor_em` = em quantas instâncias A teve penalidade menor que B. Holm sobre 4 pares planejados.\n")
    for s in SCEN:
        st_, p_, w_, n_ = rob_fr[s]
        L.append(f"- Friedman, {SCEN_PT[s]}: χ² = {st_:.1f}, p = {p_:.3g}, W = {w_:.2f} ({n_} blocos).")
    L.append("")
    L.append(md(rob))
    L.append("\n## Penalidade média por tamanho (IC 95% entre instâncias; aceitação e tempo)\n")
    for s in SCEN:
        L.append(f"### {SCEN_PT[s]}\n")
        L.append(md(desc[desc.scen == s].drop(columns=["scen"])))
        L.append("")
    L.append("## Tempo de execução (hipótese do artigo: < 1 s)\n")
    L.append(md(tdf))
    L.append("\nFiguras: `fig_penalidade_por_tamanho.png`, `fig_diferenca_vs_gcb.png`, `fig_tempo.png`.\n")
    L.append("## Ressalvas\n")
    L.append("- Instâncias sintéticas geradas por semente; resultados valem para essa família de instâncias.\n"
             "- A WF foi escolhida entre duas variações em um piloto com outra semente; a avaliação aqui usa instâncias novas.\n"
             "- Um único valor de α (0,999) e um único hardware; os tempos dependem da máquina.\n"
             "- GCB e WF são determinísticas: cada bloco tem um único valor para elas.\n"
             "- Com poucos blocos por tamanho, os testes por tamanho têm menos poder que os globais.\n")
    with open(os.path.join(out, "relatorio.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("relatorio:", os.path.join(out, "relatorio.md"))


if __name__ == "__main__":
    main()
