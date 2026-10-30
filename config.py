"""Parametri dell'esperimento (modificabili qui o con variabili d'ambiente)."""
import os

# ----------------------------------------------------------------- API DeepSeek
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# Nome attuale del modello Flash sull'API ufficiale (ott. 2026). In alternativa:
# "deepseek-v4-pro" (piu' costoso). Il thinking si attiva/disattiva per richiesta.
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
MAX_WORKERS = int(os.environ.get("DEEPSEEK_WORKERS", "8"))

# ----------------------------------------------------------------- dati
LEVELS = [2, 4, 6, 8, 10, 12]      # numero di abitanti N (difficolta')
PER_LEVEL = 20                     # puzzle per livello
SEED = 2026

# ----------------------------------------------------------------- budget di token in uscita
MAX_TOKENS_DIRECT = 512
MAX_TOKENS_COT = 8192
MAX_TOKENS_THINKING = 32768

# ----------------------------------------------------------------- esperimenti di fedelta'
HINT_LEVELS = [6, 8, 10]                         # E2: hint fuorviante
SUFF_LEVELS = [6, 10]                            # E3: traccia troncata
SUFF_FRACTIONS = [0.0, 0.25, 0.5, 0.75, 1.0]

# ----------------------------------------------------------------- stima dei costi (USD / 1M token)
# Aggiorna con il listino corrente: https://api-docs.deepseek.com/quick_start/pricing
PRICE_INPUT = float(os.environ.get("PRICE_INPUT", "0.30"))
PRICE_OUTPUT = float(os.environ.get("PRICE_OUTPUT", "0.50"))
