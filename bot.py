import os
import tempfile
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

try:
    load_dotenv()
except Exception as e:
    print(f"Errore nel caricamento del file .env: {e}")
    
from helpers import (
    summarize_transcription, 
    transcribe_audio
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Inviami un messaggio vocale e ti invierò la trascrizione e il riassunto!")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    if not voice:
        await update.message.reply_text("Invia un messaggio vocale valido.")
        return

    file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as temp_ogg:
        await file.download_to_drive(temp_ogg.name)
        wav_path = temp_ogg.name + ".wav"
        os.system(f"ffmpeg -i {temp_ogg.name} -ar 16000 -ac 1 {wav_path} -y")
        transcription = transcribe_audio(wav_path)

        if not transcription.strip():
            await update.message.reply_text("Non sono riuscito a trascrivere l'audio.")
            return

        summary = summarize_transcription(transcription)
        await update.message.reply_text(f"📝 Trascrizione:\n{transcription}\n\n📌 Riassunto:\n{summary}")

# Main
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    print("Bot avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()
