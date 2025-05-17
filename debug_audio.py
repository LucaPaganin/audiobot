import sys
from dotenv import load_dotenv

load_dotenv()
# Importa le librerie necessarie
from helpers import transcribe_audio, summarize_transcription

# Verifica input
if len(sys.argv) < 2:
    print("❌ Usa: python debug_audio.py <file_audio.wav>")
    sys.exit(1)

input_audio_path = sys.argv[1]

# Trascrizione
trascrizione = transcribe_audio(input_audio_path)
print("\n📄 Trascrizione:")
print(trascrizione)

# Riassunto
if trascrizione and not trascrizione.startswith("Errore"):
    print("\n🧠 Riassunto:")
    riassunto = summarize_transcription(trascrizione)
    print(riassunto)
else:
    print("\n⚠️ Impossibile riassumere: la trascrizione è vuota o non valida.")
