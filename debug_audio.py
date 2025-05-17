import sys
from dotenv import load_dotenv

load_dotenv()
# Importa le librerie necessarie
import helpers

# Verifica input
if len(sys.argv) < 2:
    print("❌ Usa: python debug_audio.py <file_audio.wav>")
    sys.exit(1)

input_audio_path = sys.argv[1]

result = helpers.transcribe_audio_azure(input_audio_path)

print("\n📄 Trascrizione:")
print(result)

# # Riassunto
# if trascrizione and not trascrizione.startswith("Errore"):
#     print("\n🧠 Riassunto:")
#     riassunto = helpers.summarize_transcription(trascrizione)
#     print(riassunto)
# else:
#     print("\n⚠️ Impossibile riassumere: la trascrizione è vuota o non valida.")
