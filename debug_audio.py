#!/usr/bin/env python3
"""
Script di debug per testare le funzioni di elaborazione dell'audio
senza dover utilizzare il bot Telegram.
"""

import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

try:
    load_dotenv()
except Exception as e:
    print(f"Errore nel caricamento del file .env: {e}")

from helpers import (
    transcribe_audio_chunks,
    split_text_for_telegram,
    get_wav_duration
)


def main():
    if len(sys.argv) < 2:
        print("Uso: python debug_audio.py <percorso_file_audio>")
        return

    audio_path = sys.argv[1]
    file_path = Path(audio_path)
    
    if not file_path.exists():
        print(f"Errore: il file {audio_path} non esiste.")
        return
    
    if file_path.suffix.lower() not in ['.wav', '.ogg']:
        print(f"Errore: il file deve essere in formato .wav o .ogg")
        return
    
    print(f"Elaborazione del file: {file_path}")
    
    if file_path.suffix.lower() == '.wav':
        duration = get_wav_duration(str(file_path))
        print(f"Durata file: {duration:.2f} secondi")
    
    # Misura del tempo di elaborazione
    start_time = time.time()
    
    # Elaborazione dell'audio
    result, is_summary = transcribe_audio_chunks(str(file_path))
    
    elapsed_time = time.time() - start_time
    print(f"Tempo di elaborazione: {elapsed_time:.2f} secondi")
    print(f"Risultato è un riassunto: {'Sì' if is_summary else 'No'}")
    
    # Dividi il risultato per verificare la funzione split_text_for_telegram
    text_parts = split_text_for_telegram(result)
    
    print(f"Il testo è stato diviso in {len(text_parts)} parti")
    
    # Stampa il risultato
    print("\n" + "=" * 50)
    print("RISULTATO:")
    print("=" * 50 + "\n")
    
    for i, part in enumerate(text_parts):
        print(f"--- PARTE {i+1}/{len(text_parts)} ---")
        print(part)
        print("\n")


if __name__ == "__main__":
    main()
