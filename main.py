#!/usr/bin/env python3
"""
Chain-of-Thought e Explainable AI con le API di DeepSeek.

    export DEEPSEEK_API_KEY=sk-...
    python main.py              # esegue E1, E2, E3 + analisi -> results/ e results_for_claude.zip
    python main.py --dry-run    # stessa pipeline con un client finto (nessuna chiamata, nessun costo)
    python main.py --report     # rigenera solo grafici e tabelle dai risultati gia' salvati
"""
from __future__ import annotations

import argparse
import json
import os
import zipfile

import config as cfg
from analysis import run as analyse
from experiments import run_e1, run_e2, run_e3
from puzzles import build_dataset, load, save

HERE = os.path.dirname(os.path.abspath(__file__))


def write_jsonl(rows, path):
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def pack(res_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(res_dir):
            for f in files:
                if f.endswith(".png"):
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, os.path.dirname(res_dir)))
    print(f"[pack] {zip_path} ({os.path.getsize(zip_path) / 1e6:.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="client finto, nessuna chiamata API")
    ap.add_argument("--report", action="store_true", help="solo analisi dei risultati esistenti")
    ap.add_argument("--per-level", type=int, default=cfg.PER_LEVEL)
    args = ap.parse_args()

    res_dir = os.path.join(HERE, "results_dryrun" if args.dry_run else "results")
    os.makedirs(res_dir, exist_ok=True)

    if not args.report:
        data_path = os.path.join(res_dir, "puzzles.jsonl")
        if os.path.exists(data_path):
            puzzles = load(data_path)
        else:
            puzzles = build_dataset(cfg.LEVELS, args.per_level, cfg.SEED)
            save(puzzles, data_path)
        print(f"[data] {len(puzzles)} puzzle, livelli N={cfg.LEVELS}")

        if args.dry_run:
            from mock_client import MockClient
            client = MockClient(puzzles)
        else:
            if not cfg.API_KEY:
                raise SystemExit("Imposta la variabile d'ambiente DEEPSEEK_API_KEY (oppure usa --dry-run).")
            from deepseek_client import DeepSeekClient
            client = DeepSeekClient(cfg.MODEL, cfg.BASE_URL, cfg.API_KEY,
                                    os.path.join(res_dir, "api_cache.jsonl"), cfg.MAX_WORKERS)
        print(f"[api] modello: {client.model}")

        e1 = run_e1(client, puzzles, cfg)
        write_jsonl(e1, os.path.join(res_dir, "e1.jsonl"))
        e2 = run_e2(client, puzzles, e1, cfg)
        write_jsonl(e2, os.path.join(res_dir, "e2.jsonl"))
        e3 = run_e3(client, puzzles, e1, cfg)
        write_jsonl(e3, os.path.join(res_dir, "e3.jsonl"))
        with open(os.path.join(res_dir, "run_info.json"), "w") as fh:
            json.dump(dict(model=client.model, base_url=cfg.BASE_URL, levels=cfg.LEVELS,
                           per_level=args.per_level, dry_run=args.dry_run), fh, indent=2)

    s = analyse(res_dir, cfg.PRICE_INPUT, cfg.PRICE_OUTPUT)
    print("\n=== Riepilogo E1 (accuratezza per N) ===")
    for cond, d in s["e1"].items():
        accs = "  ".join(f"N={n}:{v['acc']:.2f}" for n, v in d["per_n"].items())
        print(f"{cond:11s} tot={d['acc']:.2f}  {accs}  costo~${d['cost_usd']:.2f}")
    if "all" in s["e2"]:
        d = s["e2"]["all"]
        print(f"E2 hint: segue={d['follow']:.2f} influenzato={d['influenced']:.2f} "
              f"fedelta'={d['faithfulness']}")
    pack(res_dir, os.path.join(HERE, "results_dryrun.zip" if args.dry_run else "results_for_analysis.zip"))


if __name__ == "__main__":
    main()
