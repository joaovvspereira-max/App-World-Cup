"""Repair script for stale palpites.pontos values.

Run this once from the app root to recompute and persist points for all
finished matches.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from database.palpites import reparar_todos_pontos


if __name__ == "__main__":
    print("Repairing stored palpites.pontos for all finished matches...")
    result = reparar_todos_pontos()
    print("Done.")
    print(f"Processed: {result.get('processed', 0)}")
    print(f"Updated:   {result.get('updated', 0)}")
    print(f"Errors:    {result.get('errors', 0)}")
