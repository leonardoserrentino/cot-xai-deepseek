"""
Generatore di puzzle "Knights and Knaves" (Smullyan, 1978) a difficolta' controllata.

Ogni abitante e' un cavaliere (dice sempre il vero) o un furfante (mente sempre).
Associando a ogni abitante i una variabile booleana x_i (True = cavaliere), il puzzle
e' il sistema   x_i <-> phi_i(x)   per i = 1..N.
Un puzzle viene accettato solo se ha UNA sola soluzione (verifica per forza bruta su 2^N
assegnamenti): la risposta e' quindi verificabile automaticamente e i puzzle, generati
ex novo, non possono essere stati visti dal modello durante il pre-training.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
from dataclasses import asdict, dataclass

NAMES = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry", "Isabel", "Jack",
         "Kevin", "Laura", "Mason", "Nora", "Oliver", "Paula", "Rachel", "Samuel", "Tina", "Victor"]


# ------------------------------------------------------------------ formule
# ("K", i) i e' cavaliere | ("N", i) i e' furfante | ("and"/"or"/"imp"/"iff", a, b)
# ("same"/"diff", i, j)   | ("exactly", k, [i, j, ...])
def evaluate(f, x) -> bool:
    op = f[0]
    if op == "K":
        return x[f[1]]
    if op == "N":
        return not x[f[1]]
    if op == "and":
        return evaluate(f[1], x) and evaluate(f[2], x)
    if op == "or":
        return evaluate(f[1], x) or evaluate(f[2], x)
    if op == "imp":
        return (not evaluate(f[1], x)) or evaluate(f[2], x)
    if op == "iff":
        return evaluate(f[1], x) == evaluate(f[2], x)
    if op == "same":
        return x[f[1]] == x[f[2]]
    if op == "diff":
        return x[f[1]] != x[f[2]]
    if op == "exactly":
        return sum(x[i] for i in f[2]) == f[1]
    raise ValueError(op)


def render(f, speaker: int, names: list[str]) -> str:
    """Traduce la formula in una frase inglese pronunciata da `speaker`."""
    def who(i):
        return "I" if i == speaker else names[i]

    def atom(i, knight):
        return f"{who(i)} {'am' if i == speaker else 'is'} a {'knight' if knight else 'knave'}"

    op = f[0]
    if op in ("K", "N"):
        return atom(f[1], op == "K")
    a = lambda g: render(g, speaker, names)  # noqa: E731
    if op == "and":
        return f"{a(f[1])} and {a(f[2])}"
    if op == "or":
        return f"{a(f[1])} or {a(f[2])}"
    if op == "imp":
        return f"if {a(f[1])} then {a(f[2])}"
    if op == "iff":
        return f"{a(f[1])} if and only if {a(f[2])}"
    if op in ("same", "diff"):
        x, y = who(f[1]), who(f[2])
        if y == "I":
            x, y = y, x
        return f"{y} and {x} are of {'the same type' if op == 'same' else 'different types'}"
    if op == "exactly":
        group = [names[i] for i in f[2]]
        num = {1: "one", 2: "two"}[f[1]]
        return f"exactly {num} of {', '.join(group[:-1])} and {group[-1]} " + \
               ("is a knight" if f[1] == 1 else "are knights")
    raise ValueError(op)


def random_statement(rng: random.Random, speaker: int, n: int):
    others = [i for i in range(n) if i != speaker]

    def leaf():
        return ("K" if rng.random() < 0.5 else "N", rng.choice(others if rng.random() > 0.1 else range(n)))

    kind = rng.choices(["atom", "and", "or", "imp", "iff", "same", "diff", "exactly"],
                       weights=[15, 13, 13, 13, 12, 10, 10, 14 if n >= 4 else 0])[0]
    if kind == "atom":
        return leaf()
    if kind in ("and", "or", "imp", "iff"):
        return (kind, leaf(), leaf())
    if kind in ("same", "diff"):
        i, j = rng.sample(others, 2) if len(others) >= 2 and rng.random() > 0.2 else (speaker, rng.choice(others))
        return (kind, i, j)
    group = sorted(rng.sample(others, 3))
    return ("exactly", rng.choice([1, 2]), group)


@dataclass
class Puzzle:
    id: str
    n: int
    names: list
    solution: list          # True = cavaliere
    text: str

    def solution_text(self, assignment=None) -> str:
        a = self.solution if assignment is None else assignment
        return "\n".join(f"({k + 1}) {nm} is a {'knight' if s else 'knave'}"
                         for k, (nm, s) in enumerate(zip(self.names, a)))


def make_puzzle(rng: random.Random, n: int) -> Puzzle:
    while True:
        names = rng.sample(NAMES, n)
        stmts = [random_statement(rng, i, n) for i in range(n)]
        sols = []
        for x in itertools.product([True, False], repeat=n):
            if all(x[i] == evaluate(stmts[i], x) for i in range(n)):
                sols.append(list(x))
                if len(sols) > 1:
                    break
        if len(sols) != 1:
            continue
        said = " ".join(f'{names[i]} says: "{render(s, i, names)[0].upper() + render(s, i, names)[1:]}."'
                        for i, s in enumerate(stmts))
        text = ("A very special island is inhabited only by knights and knaves. Knights always tell the "
                f"truth, and knaves always lie. You meet {n} inhabitants: {', '.join(names[:-1])} and "
                f"{names[-1]}. {said} So who is a knight and who is a knave?")
        return Puzzle(hashlib.sha1(text.encode()).hexdigest()[:10], n, names, sols[0], text)


def build_dataset(levels: list[int], per_level: int, seed: int) -> list[Puzzle]:
    rng = random.Random(seed)
    return [make_puzzle(rng, n) for n in levels for _ in range(per_level)]


def save(puzzles, path):
    with open(path, "w") as fh:
        for p in puzzles:
            fh.write(json.dumps(asdict(p)) + "\n")


def load(path) -> list[Puzzle]:
    with open(path) as fh:
        return [Puzzle(**json.loads(line)) for line in fh if line.strip()]


if __name__ == "__main__":
    p = make_puzzle(random.Random(0), 4)
    print(p.text, "\n", p.solution_text(), sep="")
