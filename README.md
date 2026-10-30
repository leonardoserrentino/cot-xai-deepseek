# Chain-of-Thought and Explainable AI with the DeepSeek API

A small experimental framework that queries **the same DeepSeek model with and without
reasoning** and evaluates its Chain-of-Thought (CoT) as an explanation, from an Explainable AI
perspective.

The central question is not whether reasoning improves accuracy — it does — but whether the
reasoning trace is a *faithful* account of how the answer was produced. A trace can be fluent,
plausible and entirely disconnected from the computation that generated the output. This code
tests that empirically along three axes: **usefulness**, **faithfulness** and **sufficiency**.

This repository accompanies a chapter of a university paper on Explainable AI for Large Language
Models (Natural Language Processing course). It includes the complete set of results from the run
described in that chapter, so the findings can be inspected without spending anything; see
[Included results](#included-results).

---

## The three experiments

| | Question | Method |
|---|---|---|
| **E1** Usefulness | Does reasoning improve answers, and where does it stop being enough? | Direct answer vs prompted CoT vs native thinking, on logic puzzles of increasing difficulty |
| **E2** Faithfulness | Does the trace disclose the factors that actually influenced the answer? | A wrong solution is planted in the prompt, attributed to an authority. Does the model follow it? Does it admit to it in the trace? |
| **E3** Sufficiency | Can the answer be reconstructed by reading the trace? | A non-thinking model is given 0–100% of the original trace and must answer |

All three use **one model**, with reasoning switched on or off per request. This matters: the
comparison is controlled at equal weights, so any difference is attributable to the reasoning
itself rather than to a different model.

### The task

*Knights and Knaves* puzzles (Smullyan). On an island every inhabitant is either a knight, who
always tells the truth, or a knave, who always lies, and each makes a statement about the others
(`Bob is a knave and Carol is a knight`). The solver must determine who is what.

Puzzles are generated at runtime from a grammar of logical connectives and accepted only if the
solution is unique, verified by brute force over all `2^N` assignments. This gives three
properties that matter for the experiment:

- **Automatically verifiable correctness** — no human grading, no LLM judge.
- **Tunable difficulty** — controlled by the number of inhabitants `N`.
- **No contamination** — the puzzles are generated fresh and cannot appear in any training set.

---

## Repository contents

```
config.py             all experiment parameters (model, levels, token budgets, pricing)
puzzles.py            puzzle generator, truth evaluation, uniqueness check
deepseek_client.py    API client: thinking on/off, on-disk cache, parallel requests
experiments.py        prompts, answer parsing, E1 / E2 / E3 runners
analysis.py           metrics, figures, LaTeX tables, qualitative examples
mock_client.py        fake client used by --dry-run (produces meaningless numbers)
main.py               entry point, runs everything
requirements.txt      dependencies
results/              complete results of the reference run (see below)
```

---

## Requirements

- Python 3.9 or newer
- An internet connection and a DeepSeek API key

Install the dependencies:

```bash
pip install -r requirements.txt
```

**Important:** the `openai` package must be version 1.x. Version 2 and later changed the internal
HTTP stack and will fail with `TypeError: process() takes no keyword arguments` on every request.
The requirements file pins this (`openai>=1.40,<2`), but if you installed the package separately,
force the correct range:

```bash
pip install 'openai>=1.40,<2'
```

---

## Getting an API key

1. Create an account at [platform.deepseek.com](https://platform.deepseek.com).
2. Open **API Keys** in the sidebar and choose **Create new API key**. Copy it immediately; it is
   shown only once. Keys begin with `sk-`.
3. Top up the balance. DeepSeek is pay-as-you-go with prepaid credit, with no subscription.

Export the key as an environment variable. The code never reads it from anywhere else, and the
key is never written to any output file.

```bash
export DEEPSEEK_API_KEY=sk-...
```

On Windows PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="sk-..."
```

---

## Running

Verify the pipeline first, without spending anything. This uses a fake client that returns
synthetic responses in the DeepSeek format; it exercises every code path end to end in a few
seconds and writes to `results_dryrun/`. **The numbers it produces are meaningless** and exist
only to confirm that the plumbing works.

```bash
python main.py --dry-run
```

Then run the real thing:

```bash
export DEEPSEEK_API_KEY=sk-...
python main.py
```

Regenerate only the figures and tables from results already on disk, without any API call:

```bash
python main.py --report
```

Run a smaller, cheaper version by reducing the number of puzzles per difficulty level:

```bash
python main.py --per-level 5
```

### Cost and runtime

The reference run made **620 API calls** and cost **USD 0.41** in total. It takes roughly **one
hour** with the default 8 parallel workers, the great majority of which is spent waiting on the
long thinking traces at the harder levels.

The breakdown is 360 calls for E1 (120 puzzles times 3 conditions), 60 for E2 and 200 for E3.
Cost is estimated locally from the token counts returned by the API, using the prices in
`config.py` (USD 0.30 per million input tokens, USD 0.50 per million output tokens). Those
defaults should be checked against the
[current price list](https://api-docs.deepseek.com/quick_start/pricing), since they change.
Budgeting USD 5 of credit is more than enough.

Every response is cached in `results/api_cache.jsonl`, keyed by a hash of the model, the prompt,
the thinking flag and the token budget. **If the run is interrupted, just launch it again**: it
resumes where it stopped and does not pay twice for calls already made. Deleting that file forces
a full re-run.

---

## Output

Everything is written to `results/`, and the same content, minus the PNG previews, is zipped into
`results_for_analysis.zip` for convenient sharing.

### Figures (`results/figures/`)

Produced as both PDF, for inclusion in LaTeX, and PNG, for quick viewing.

- **`fig_e1_accuracy_cost.pdf`** — (a) accuracy against the number of inhabitants `N`, with 95%
  Wilson confidence bands and the random-guessing baseline `2^-N`; (b) median generated tokens on
  a logarithmic scale.
- **`fig_e3_sufficiency_error.pdf`** — (a) agreement with the original answer as a function of how
  much of the trace was supplied; (b) the error signature: generated tokens against reflection
  marker density, with correct and incorrect answers separated.

### Tables (`results/tables/`)

LaTeX fragments, ready to `\input`. They emit only a `tabular` environment, so the caption, label
and float belong in the surrounding document. Numbers are formatted with the Italian decimal
comma.

- **`tab_e1.tex`** — per condition: overall accuracy, accuracy at the hardest level, median tokens
  for correct versus incorrect answers, reflection markers per thousand words, cost.
- **`tab_e2.tex`** — per difficulty level: accuracy with and without the hint, how often the hint
  is followed, how often it is mentioned, and the token cost of the hint.

### Data

- **`summary.json`** — every computed metric, the source for the figures and tables.
- **`puzzles.jsonl`** — the generated dataset: `id`, `n`, `names`, `solution`, `text`.
- **`e1.jsonl`** — one row per call (360). Fields include `condition`
  (`direct` / `cot_prompt` / `thinking`), `n`, `puzzle_id`, `pred`, `correct`, `parsed`,
  `trace` (the full reasoning), `answer_text`, `prompt_tokens`, `completion_tokens`,
  `reasoning_tokens`, `finish_reason`, `words`, `reflections`, `refl_per_1k`.
- **`e2.jsonl`** — one row per call (60). Adds `hint` (the misleading solution),
  `baseline_correct`, `follows_hint`, `influenced` (answer moved to the hint when the baseline
  answer differed), `mentions_hint`, `mentions_hint_answer`.
- **`e3.jsonl`** — one row per call (200). Adds `fraction` (how much of the trace was given),
  `kept_sentences`, `total_sentences`, `original_correct`, `agrees`.
- **`api_cache.jsonl`** — the raw cache, one record per distinct request, with `reasoning`,
  `content`, token counts and `latency`. This is what makes the run resumable.
- **`run_info.json`** — model, base URL, levels and whether the run was a dry run.
- **`examples.md`** — selected traces in readable form: a correct chain with self-verification, a
  failure at the hardest level, and any case where the hint was followed.

---

## Included results

`results/` contains the complete reference run: model `deepseek-flash`, 120 puzzles across
`N` in `{2, 4, 6, 8, 10, 12}`, seed 2026. The raw traces are included, so every number can be
audited back to the response that produced it. The headline findings:

**Reasoning is not decorative, it is the computation.** Without it, accuracy collapses from 85% at
`N=2` to 0% from `N=6` onwards, falling onto the random-guessing curve. Prompted CoT reaches 96.7%
overall, and native thinking reaches 100% at every level, with no truncated traces. The same
weights, the same model: the only difference is being allowed to write before answering. The cost
is explicit, at roughly 26 times the tokens of a direct answer.

**Errors announce themselves.** Native thinking produced no errors at all, so failures can only be
studied in the prompted-CoT condition, where there are 4 out of 120. They are not
indistinguishable from successes: incorrect traces are about 3.6 times longer (4,889 against 1,350
median tokens) and four times denser in reflection markers (10.0 against 2.5 per thousand words).
This is the most practically useful result here, because it is observable **without knowing the
correct answer**.

**The trace is load-bearing, not a post-hoc rationalization.** With no trace, agreement is zero at
both levels; with the full trace it is 100%. In between, growth is gradual and slower for harder
puzzles: at half the trace, agreement is 65% for `N=6` but only 30% for `N=10`. The answer forms
as the trace proceeds, which is the opposite of the early-answering pattern that would indicate
rationalization.

**The misleading hint fails to deceive, but leaves a measurable mark.** The model adopts the
planted solution once in 60 attempts, and accuracy falls only from 100% to 98%. It mentions the
hint in all 60 cases, including the 59 where it rejects it, and refuting it costs 54% more tokens
(1,822 to 2,805 median). Note that this is **not** a confirmation that CoT is faithful: the
faithfulness metric rests on a single influenced case and therefore means nothing statistically.
The test lost its power because the model resisted the manipulation. That single case is in
`examples.md` and is worth reading: the model solves the puzzle, detects the contradiction, and
openly deliberates before deciding to defer to the stated authority.

### Reproducing them

The dataset is generated from a fixed seed, so the puzzles are identical on any machine. The model
responses are not deterministic, so the numbers will be close but not identical.

```bash
export DEEPSEEK_API_KEY=sk-...
rm -rf results
python main.py
```

To regenerate the figures and tables from the included results without calling the API at all:

```bash
python main.py --report
```

---

## Configuration

Everything lives in `config.py`, and the most useful settings can also be overridden by
environment variable.

| Setting | Default | Notes |
|---|---|---|
| `DEEPSEEK_MODEL` | `deepseek-flash` | Currently served by DeepSeek-V4.1-Flash. `deepseek-v4-pro` also works and costs more |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible endpoint |
| `DEEPSEEK_WORKERS` | `8` | Parallel requests. Lower it if you hit rate limits |
| `PRICE_INPUT` / `PRICE_OUTPUT` | `0.30` / `0.50` | USD per million tokens, for the cost estimate only |
| `LEVELS` | `[2, 4, 6, 8, 10, 12]` | Difficulty levels. If the model solves everything at `N=12`, add higher levels |
| `PER_LEVEL` | `20` | Puzzles per level; also settable with `--per-level` |
| `SEED` | `2026` | Dataset generation seed |
| `HINT_LEVELS` | `[6, 8, 10]` | Levels used for E2 |
| `SUFF_LEVELS`, `SUFF_FRACTIONS` | `[6, 10]`, `[0, .25, .5, .75, 1]` | Levels and trace fractions for E3 |
| `MAX_TOKENS_*` | 512 / 8192 / 32768 | Output budget for direct, prompted CoT and thinking |

---

## Notes and caveats

**The model is no longer R1.** DeepSeek retired the `deepseek-reasoner` and `deepseek-chat`
endpoints in July 2026. The current API serves `deepseek-flash`, which inherits the same
reasoning-model paradigm. This is in one respect an advantage: the same model can be queried with
and without reasoning, which makes the comparison in E1 controlled at equal weights. Reasoning is
toggled per request through `extra_body={"thinking": {"type": "enabled" | "disabled"}}`, and the
trace comes back in a separate `reasoning_content` field rather than mixed into the answer. Note
that `temperature` is ignored in thinking mode, so the code only sets it when thinking is off.

**The tests are behavioural.** They observe how the output changes as the input and the trace
change, which establishes *necessary* conditions for faithfulness, not sufficient ones. That the
trace is enough to reproduce the answer does not prove it caused the answer. Only mechanistic
methods can verify whether the internal computation matches the text.

**The findings are scoped to this task.** Knights and Knaves puzzles have a unique, verifiable
solution, which favours deduction over heuristics and is exactly the setting where reasoning is
instrumental to being correct, and therefore where one would expect it to be faithful. Results on
subjective or unverifiable tasks could differ substantially.

**Traces are not written for human readers.** They come back in terse, ungrammatical English
(`We need solve logic. Need be careful.`), a working scratchpad optimized for the model's own use.
Legibility is a side effect of training, not a guarantee, and it should not be confused with
faithfulness.
