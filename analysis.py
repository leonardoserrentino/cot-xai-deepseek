"""
Metriche, grafici (PDF+PNG), tabelle LaTeX ed esempi qualitativi a partire da results/*.jsonl.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# stile coerente con un documento LaTeX; colori fissi per condizione
COND = {"direct": ("Risposta diretta", "#eb6834"),
        "cot_prompt": ("CoT da prompt", "#eda100"),
        "thinking": ("Thinking nativo", "#2a78d6")}
INK, INK2 = "#0b0b0b", "#52514e"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9, "legend.fontsize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.frameon": False,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e4e3df",
    "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.edgecolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "lines.linewidth": 1.8, "lines.markersize": 4.5,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})
W = 6.2   # larghezza in pollici (~\textwidth con margini di 2.5 cm)


def load_rows(path):
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def wilson(k, n, z=1.96):
    """Intervallo di confidenza di Wilson al 95% per una proporzione."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def median(xs):
    xs = [x for x in xs if x is not None]
    return float(np.median(xs)) if xs else None


# ================================================================== riepilogo numerico
def summarize(e1, e2, e3, price_in, price_out):
    s = {"e1": {}, "e2": {}, "e3": {}}
    for cond in COND:
        rs = [r for r in e1 if r["condition"] == cond]
        if not rs:
            continue
        per_n = {}
        for n in sorted({r["n"] for r in rs}):
            g = [r for r in rs if r["n"] == n]
            k = sum(r["correct"] for r in g)
            lo, hi = wilson(k, len(g))
            per_n[n] = dict(acc=k / len(g), lo=lo, hi=hi, n=len(g),
                            tokens_median=median([r["completion_tokens"] for r in g]),
                            truncated=mean([r["finish_reason"] == "length" for r in g]))
        cost = sum(r["prompt_tokens"] * price_in + r["completion_tokens"] * price_out for r in rs) / 1e6
        s["e1"][cond] = dict(
            per_n=per_n, acc=mean([r["correct"] for r in rs]),
            tokens_median=median([r["completion_tokens"] for r in rs]),
            tokens_correct=median([r["completion_tokens"] for r in rs if r["correct"]]),
            tokens_wrong=median([r["completion_tokens"] for r in rs if not r["correct"]]),
            refl_per_1k=mean([r["refl_per_1k"] for r in rs if r["words"] > 0]),
            refl_per_1k_correct=mean([r["refl_per_1k"] for r in rs if r["words"] > 0 and r["correct"]]),
            refl_per_1k_wrong=mean([r["refl_per_1k"] for r in rs if r["words"] > 0 and not r["correct"]]),
            truncated=mean([r["finish_reason"] == "length" for r in rs]),
            unparsed=mean([not r["parsed"] for r in rs]), cost_usd=cost)
    for n in sorted({r["n"] for r in e2}):
        g = [r for r in e2 if r["n"] == n]
        infl = [r for r in g if r["influenced"]]
        s["e2"][n] = dict(
            count=len(g), acc_baseline=mean([r["baseline_correct"] for r in g]),
            acc_hint=mean([r["correct"] for r in g]), follow=mean([r["follows_hint"] for r in g]),
            influenced=mean([r["influenced"] for r in g]), n_influenced=len(infl),
            mention=mean([r["mentions_hint"] for r in g]),
            faithfulness=mean([r["mentions_hint"] for r in infl]) if infl else None,
            # categorie per il grafico a barre impilate
            cat_correct=mean([r["correct"] for r in g]),
            cat_follow_declared=mean([r["follows_hint"] and r["mentions_hint"] for r in g]),
            cat_follow_hidden=mean([r["follows_hint"] and not r["mentions_hint"] for r in g]),
            cat_other=mean([not r["correct"] and not r["follows_hint"] for r in g]))
    if e2:
        infl = [r for r in e2 if r["influenced"]]
        s["e2"]["all"] = dict(count=len(e2), acc_baseline=mean([r["baseline_correct"] for r in e2]),
                              acc_hint=mean([r["correct"] for r in e2]),
                              follow=mean([r["follows_hint"] for r in e2]),
                              influenced=mean([r["influenced"] for r in e2]), n_influenced=len(infl),
                              mention=mean([r["mentions_hint"] for r in e2]),
                              faithfulness=mean([r["mentions_hint"] for r in infl]) if infl else None)
    for n in sorted({r["n"] for r in e3}):
        g = [r for r in e3 if r["n"] == n]
        fr = sorted({r["fraction"] for r in g})
        s["e3"][n] = dict(fractions=fr, count=len([r for r in g if r["fraction"] == fr[0]]),
                          agree=[mean([r["agrees"] for r in g if r["fraction"] == f]) for f in fr],
                          acc=[mean([r["correct"] for r in g if r["fraction"] == f]) for f in fr])
    return s


# ================================================================== grafici
def fig_e1(s, out):
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.45))
    for cond, (lab, col) in COND.items():
        if cond not in s["e1"]:
            continue
        pn = s["e1"][cond]["per_n"]
        ns = sorted(int(n) for n in pn)
        g = lambda k: [pn[n][k] if n in pn else pn[str(n)][k] for n in ns]  # noqa: E731
        a.fill_between(ns, g("lo"), g("hi"), color=col, alpha=0.15, lw=0)
        a.plot(ns, g("acc"), marker="o", color=col, label=lab)
        b.plot(ns, g("tokens_median"), marker="o", color=col, label=lab)
    a.plot(ns, [0.5 ** n for n in ns], ls="--", lw=1, color=INK2, label="Casuale ($2^{-N}$)")
    a.set_ylim(-0.02, 1.02); a.set_ylabel("accuratezza"); a.set_title("(a) Accuratezza", loc="left", fontweight="bold")
    b.set_yscale("log"); b.set_ylabel("token generati (mediana)")
    b.set_title("(b) Costo del ragionamento", loc="left", fontweight="bold")
    for ax in (a, b):
        ax.set_xlabel("numero di abitanti $N$"); ax.set_xticks(ns)
    h, l = a.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout()
    _save(fig, out, "fig_e1_accuracy_cost")


def fig_faith(s, out):
    fig, (a, b) = plt.subplots(1, 2, figsize=(W, 2.45))
    ramp = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
    for i, (n, d) in enumerate(sorted(s["e3"].items(), key=lambda kv: int(kv[0]))):
        c = ramp[min(i * 2 + 1, 3)] if len(s["e3"]) <= 2 else ramp[i % 4]
        a.plot(d["fractions"], d["agree"], marker="o", color=c, label=f"$N={n}$")
    a.set_ylim(-0.02, 1.02); a.set_xlabel("frazione di ragionamento fornita")
    a.set_ylabel("accordo con la risposta originale"); a.legend(loc="lower right")
    a.set_title("(a) Sufficienza della traccia (E3)", loc="left", fontweight="bold")
    levels = sorted((k for k in s["e2"] if k != "all"), key=int)
    cats = [("cat_correct", "Corretta (hint ignorato)", "#1baf7a"),
            ("cat_follow_declared", "Segue l'hint e lo dichiara", "#eda100"),
            ("cat_follow_hidden", "Segue l'hint e lo tace", "#e34948"),
            ("cat_other", "Altro errore", "#b8b7b0")]
    x = np.arange(len(levels)); bottom = np.zeros(len(levels))
    for key, lab, col in cats:
        v = np.array([s["e2"][n][key] for n in levels])
        b.bar(x, v, 0.6, bottom=bottom, color=col, label=lab, edgecolor="white", linewidth=1)
        bottom += v
    b.set_xticks(x); b.set_xticklabels([f"$N={n}$" for n in levels]); b.set_ylim(0, 1)
    b.set_ylabel("frazione delle risposte"); b.grid(axis="x", visible=False)
    b.set_title("(b) Hint fuorviante (E2)", loc="left", fontweight="bold")
    b.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), handlelength=1)
    fig.tight_layout()
    _save(fig, out, "fig_e2_e3_faithfulness")


def _save(fig, out, name):
    os.makedirs(out, exist_ok=True)
    fig.savefig(os.path.join(out, name + ".pdf"))
    fig.savefig(os.path.join(out, name + ".png"), dpi=250)
    plt.close(fig)


# ================================================================== tabelle LaTeX
def _p(x):
    return "--" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.0f}\\%"


def _t(x):
    return "--" if x is None else f"{x:,.0f}".replace(",", "\\,")


def tables(s, out):
    os.makedirs(out, exist_ok=True)
    nmax = max(int(n) for n in s["e1"]["thinking"]["per_n"]) if "thinking" in s["e1"] else None
    L = [r"\begin{tabular}{lccccc}", r"\toprule",
         rf"Condizione & Acc. & Acc. $N{{=}}{nmax}$ & Token corr.\ / err. & Rifl./1k & Costo \\",
         r"\midrule"]
    for cond, (lab, _) in COND.items():
        if cond not in s["e1"]:
            continue
        d = s["e1"][cond]
        pn = d["per_n"]
        last = pn.get(nmax, pn.get(str(nmax), {})).get("acc")
        refl = "--" if cond == "direct" else f"{d['refl_per_1k']:.1f}"
        L.append(f"{lab} & {_p(d['acc'])} & {_p(last)} & {_t(d['tokens_correct'])} / {_t(d['tokens_wrong'])} "
                 f"& {refl} & \\${d['cost_usd']:.2f} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    open(os.path.join(out, "tab_e1.tex"), "w").write("\n".join(L) + "\n")

    if s["e2"]:
        levels = sorted((k for k in s["e2"] if k != "all"), key=int) + ["all"]
        L = [r"\begin{tabular}{lcccccc}", r"\toprule",
             r"$N$ & Acc.\ senza hint & Acc.\ con hint & Segue & Influenzato & Menziona "
             r"& Fedelt\`a $\uparrow$ \\", r"\midrule"]
        for n in levels:
            d = s["e2"][n]
            if n == "all":
                L.append(r"\midrule")
            L.append(f"{'Tutti' if n == 'all' else n} & {_p(d['acc_baseline'])} & {_p(d['acc_hint'])} & "
                     f"{_p(d['follow'])} & {_p(d['influenced'])} & {_p(d['mention'])} & "
                     f"{_p(d['faithfulness'])} ({d['n_influenced']}) \\\\")
        L += [r"\bottomrule", r"\end{tabular}"]
        open(os.path.join(out, "tab_e2.tex"), "w").write("\n".join(L) + "\n")


# ================================================================== esempi qualitativi
def examples(e1, e2, out, max_chars=1800):
    def cut(t):
        return t if len(t) <= max_chars else t[: max_chars // 2] + "\n[...]\n" + t[-max_chars // 2:]
    th = [r for r in e1 if r["condition"] == "thinking"]
    pick = []
    refl = sorted([r for r in th if r["correct"] and r["reflections"] > 0], key=lambda r: (r["n"], r["words"]))
    if refl:
        pick.append(("Ragionamento corretto con auto-verifica", refl[len(refl) // 2]))
    fail = sorted([r for r in th if not r["correct"]], key=lambda r: -r["n"])
    if fail:
        pick.append(("Fallimento al livello piu' difficile", fail[0]))
    hidden = [r for r in e2 if r["influenced"] and not r["mentions_hint"]]
    declared = [r for r in e2 if r["follows_hint"] and r["mentions_hint"]]
    if hidden:
        pick.append(("Hint seguito SENZA menzionarlo (CoT non fedele)", hidden[0]))
    if declared:
        pick.append(("Hint seguito e dichiarato", declared[0]))
    with open(os.path.join(out, "examples.md"), "w") as fh:
        for title, r in pick:
            fh.write(f"## {title}\n\nN={r['n']} | corretta={r['correct']} | token={r['completion_tokens']}\n\n"
                     f"### Ragionamento\n```\n{cut(r['trace'])}\n```\n### Risposta\n```\n{r['answer_text']}\n```\n\n")


def run(res_dir, price_in, price_out):
    e1 = load_rows(os.path.join(res_dir, "e1.jsonl"))
    e2 = load_rows(os.path.join(res_dir, "e2.jsonl")) if os.path.exists(os.path.join(res_dir, "e2.jsonl")) else []
    e3 = load_rows(os.path.join(res_dir, "e3.jsonl")) if os.path.exists(os.path.join(res_dir, "e3.jsonl")) else []
    s = summarize(e1, e2, e3, price_in, price_out)
    with open(os.path.join(res_dir, "summary.json"), "w") as fh:
        json.dump(s, fh, indent=2, default=str)
    fig_e1(s, os.path.join(res_dir, "figures"))
    if e2 and e3:
        fig_faith(s, os.path.join(res_dir, "figures"))
    tables(s, os.path.join(res_dir, "tables"))
    examples(e1, e2, res_dir)
    return s
