import os
import tempfile
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
from logging_config import setup_logger

# Configurazione del logger
logger = setup_logger(__name__)

try:
    load_dotenv()
except Exception as e:
    logger.error(f"Errore nel caricamento del file .env: {e}")
    
from helpers import (
    transcribe_audio_chunks,
    split_text_for_telegram
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Inviami un messaggio vocale e ti invierò la trascrizione o il riassunto (se l'audio è lungo)!")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce i messaggi vocali ricevuti:
    1. Scarica l'audio
    2. Lo elabora (trascrive o riassume se lungo)
    3. Invia il risultato in uno o più messaggi
    """
    voice = update.message.voice
    if not voice:
        await update.message.reply_text("Invia un messaggio vocale valido.")
        return

    # Invio messaggio di elaborazione in corso
    processing_message = await update.message.reply_text("⏱️ Sto elaborando il tuo messaggio vocale...")
    
    try:
        # Scarica il file audio
        file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_ogg:
            await file.download_to_drive(temp_ogg.name)
            
            # Converti in WAV con ffmpeg (formato richiesto da Azure Speech)
            wav_path = temp_ogg.name + ".wav"
            os.system(f"ffmpeg -i {temp_ogg.name} -ar 16000 -ac 1 {wav_path} -y")
            
            # Elabora l'audio (trascrive o riassume in base alla lunghezza)
            result_text, is_summary = transcribe_audio_chunks(wav_path)
            
            # Elimina i file temporanei
            try:
                os.unlink(temp_ogg.name)
                os.unlink(wav_path)
            except:
                pass
            
            # Se non c'è nessun risultato
            if not result_text or not result_text.strip():
                await processing_message.edit_text("Non sono riuscito a trascrivere l'audio.")
                return
            
            # Dividi il risultato in messaggi più piccoli se necessario
            text_parts = split_text_for_telegram(result_text)
            
            # Invia i messaggi
            await processing_message.delete()
            
            # Prepara l'intestazione in base al tipo di elaborazione
            header = "📝 **Trascrizione:**\n\n" if not is_summary else "📌 **Riassunto dell'audio:**\n\n"
            
            # Invia il primo messaggio con l'intestazione
            await update.message.reply_text(f"{header}{text_parts[0]}")
            
            # Invia i messaggi rimanenti (se presenti)
            for part in text_parts[1:]:
                await update.message.reply_text(part)
                
    except Exception as e:
        # Gestione degli errori
        logger.error(f"Errore durante l'elaborazione dell'audio: {e}", exc_info=True)
        await processing_message.edit_text(f"Si è verificato un errore durante l'elaborazione dell'audio: {str(e)[:100]}...")


# Main
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("Errore: Token Telegram non trovato. Impostalo nel file .env come TELEGRAM_BOT_TOKEN.")
        return
        
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Bot avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()
