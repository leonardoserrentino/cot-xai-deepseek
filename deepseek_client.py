"""
Client minimale per l'API di DeepSeek (OpenAI-compatibile).

Lo stesso modello viene interrogato in due modalita':
  * thinking=True  -> il modello genera un ragionamento interno, restituito nel campo
                      separato `reasoning_content`, prima della risposta (`content`);
  * thinking=False -> il modello risponde direttamente (nessun reasoning_content).

Ogni risposta viene salvata in una cache su disco (JSONL): rilanciare lo script non
ripete le chiamate gia' fatte (e non le ripaga).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor


class DeepSeekClient:
    def __init__(self, model: str, base_url: str, api_key: str, cache_path: str, max_workers: int = 8):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=1800)
        self.model = model
        self.max_workers = max_workers
        self.cache_path = cache_path
        self.lock = threading.Lock()
        self.cache = {}
        if os.path.exists(cache_path):
            with open(cache_path) as fh:
                for line in fh:
                    rec = json.loads(line)
                    self.cache[rec["key"]] = rec

    def _key(self, user: str, thinking: bool, max_tokens: int) -> str:
        return hashlib.sha256(f"{self.model}|{thinking}|{max_tokens}|{user}".encode()).hexdigest()

    def _call(self, user: str, thinking: bool, max_tokens: int) -> dict:
        kwargs = dict(model=self.model, messages=[{"role": "user", "content": user}], max_tokens=max_tokens,
                      extra_body={"thinking": {"type": "enabled" if thinking else "disabled"}})
        if not thinking:
            kwargs["temperature"] = 0.0          # in thinking mode la temperatura e' ignorata
        for attempt in range(6):
            try:
                t0 = time.time()
                r = self.client.chat.completions.create(**kwargs)
                msg = r.choices[0].message
                extra = getattr(msg, "model_extra", None) or {}
                reasoning = getattr(msg, "reasoning_content", None) or extra.get("reasoning_content") or ""
                usage = r.usage
                details = getattr(usage, "completion_tokens_details", None)
                return dict(
                    reasoning=reasoning, content=msg.content or "",
                    finish_reason=r.choices[0].finish_reason,
                    prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
                    reasoning_tokens=getattr(details, "reasoning_tokens", None) if details else None,
                    latency=time.time() - t0,
                )
            except Exception as e:  # errori di rete / rate limit: backoff esponenziale
                wait = 5 * 2 ** attempt
                print(f"  [api] {e.__class__.__name__}: {str(e)[:150]} -> riprovo tra {wait}s", flush=True)
                time.sleep(wait)
        return dict(reasoning="", content="", finish_reason="error", prompt_tokens=0,
                    completion_tokens=0, reasoning_tokens=None, latency=0.0)

    def ask(self, user: str, thinking: bool, max_tokens: int) -> dict:
        key = self._key(user, thinking, max_tokens)
        if key in self.cache:
            return self.cache[key]
        rec = dict(key=key, model=self.model, thinking=thinking, **self._call(user, thinking, max_tokens))
        if rec["finish_reason"] != "error":
            with self.lock:
                self.cache[key] = rec
                with open(self.cache_path, "a") as fh:
                    fh.write(json.dumps(rec) + "\n")
        return rec

    def ask_many(self, jobs: list[tuple[str, bool, int]], desc: str = "") -> list[dict]:
        """Esegue le richieste in parallelo mantenendo l'ordine."""
        done = [0]

        def run(job):
            out = self.ask(*job)
            with self.lock:
                done[0] += 1
                if done[0] % 10 == 0 or done[0] == len(jobs):
                    print(f"  [{desc}] {done[0]}/{len(jobs)}", flush=True)
            return out

        with ThreadPoolExecutor(self.max_workers) as ex:
            return list(ex.map(run, jobs))
