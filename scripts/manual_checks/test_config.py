"""Inspect configuration without printing credential values. Importing this manual check never initializes the app."""

import argparse
from pathlib import Path
import sys


def run_check():
    import privacy_bootstrap
    from config import config

    print("--- Configuratie Test ---")
    print(f"Ollama URL: {config.OLLAMA_BASE_URL}")
    print(f"Model: {config.OLLAMA_MODEL}")
    print(f"Workspace Path: {config.WORKSPACE_ROOT}")
    print(f"Telegram Token geladen: {('Ja' if config.TELEGRAM_BOT_TOKEN else 'Nee')}")
    print("Configuratie is succesvol geladen!")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    run_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
