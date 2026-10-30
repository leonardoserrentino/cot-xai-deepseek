"""
Client FINTO per `python main.py --dry-run`: non chiama nessuna API e produce risposte
sintetiche (pseudo-casuali) con lo stesso formato di DeepSeek. Serve solo a verificare
che la pipeline giri e a vedere l'impaginazione dei grafici. I numeri NON hanno valore.
"""
from __future__ import annotations

import hashlib
import random
import re


class MockClient:
    def __init__(self, puzzles):
        self.puzzles = puzzles
        self.model = "mock"

    def _find(self, user):
        return next(p for p in self.puzzles if p.text in user)

    def ask(self, user, thinking, max_tokens):
        rng = random.Random(hashlib.md5(user.encode()).hexdigest())
        p = self._find(user)
        reader = "<reasoning>" in user
        hint = None
        m = re.search(r"correct solution is: (.*)\.$", user)
        if m:
            hint = [("knight" in part) for part in m.group(1).split(", ")]
        if reader:
            trace = user.split("<reasoning>")[1]
            frac = min(1.0, len(trace) / 2500)
            p_ok = 0.45 ** (p.n / 4) + (1 - 0.45 ** (p.n / 4)) * frac
            reasoning = ""
        elif thinking:
            p_ok = max(0.05, 1.0 - 0.07 * max(0, p.n - 4))
            reasoning = self._fake_trace(p, rng, 40 + 25 * p.n)
        elif "step by step" in user:
            p_ok = max(0.02, 0.95 - 0.13 * (p.n - 2))
            reasoning = self._fake_trace(p, rng, 10 + 6 * p.n)
        else:
            p_ok = 0.5 ** (p.n / 2.5)
            reasoning = ""
        ans = list(p.solution)
        if hint is not None and rng.random() < 0.3:
            ans = hint
            reasoning += "" if rng.random() < 0.6 else " The professor says otherwise, so I will trust the professor."
        elif rng.random() > p_ok:
            i = rng.randrange(p.n)
            ans[i] = not ans[i]
        truncated = thinking and rng.random() < 0.02 * max(0, p.n - 6)
        content = "" if truncated else "<answer>\n" + p.solution_text(ans) + "\n</answer>"
        if not thinking and reasoning:
            content = reasoning + "\n" + content
            reasoning = ""
        n_tok = int(len((reasoning + content).split()) * 1.4) + 5
        return dict(key="", model="mock", thinking=thinking, reasoning=reasoning, content=content,
                    finish_reason="length" if truncated else "stop", prompt_tokens=len(user.split()),
                    completion_tokens=n_tok, reasoning_tokens=None, latency=0.0)

    @staticmethod
    def _fake_trace(p, rng, n_sent):
        out = []
        for _ in range(n_sent):
            a, b = rng.sample(p.names, 2)
            out.append(rng.choice([
                f"Suppose {a} is a knight. Then {b} must be a knave.",
                f"If {a} is a knave, the statement is false, so {b} is a knight.",
                f"Wait, let me check {a} again.", f"This leads to a contradiction for {b}.",
                f"So {a} is a {'knight' if rng.random() < .5 else 'knave'}."]))
        return " ".join(out)

    def ask_many(self, jobs, desc=""):
        return [self.ask(*j) for j in jobs]
