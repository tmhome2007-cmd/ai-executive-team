"""Regression checks for config."""

# test_config.py
from config import config

print("--- Configuratie Test ---")
print(f"Ollama URL: {config.OLLAMA_BASE_URL}")
print(f"Model: {config.OLLAMA_MODEL}")
print(f"Workspace Path: {config.WORKSPACE_ROOT}")
print(f"Telegram Token geladen: {'Ja' if config.TELEGRAM_BOT_TOKEN else 'Nee'}")
print("Configuratie is succesvol geladen!")
