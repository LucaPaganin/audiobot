import os
import tempfile
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import concurrent.futures
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
    transcribe_audio_chunks_async,
    split_text_for_telegram,
    convert_audio_to_wav,
    summarize_transcription
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Inviami un messaggio vocale e ti invierò la trascrizione!")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce i messaggi vocali ricevuti:
    1. Scarica l'audio
    2. Lo elabora (trascrive o riassume se lungo)
    3. Invia il risultato in uno o più messaggi
    """
    if update.message.voice:
        file = await context.bot.get_file(update.message.voice.file_id)
    elif update.message.audio:
        file = await context.bot.get_file(update.message.audio.file_id)
    else:
        await update.message.reply_text("Invia un messaggio vocale o un audio validi.")
        return

    # Invio messaggio di elaborazione in corso
    processing_message = await update.message.reply_text("⏱️ Sto elaborando il tuo messaggio vocale...")
    
    try:
        # Scarica il file audio
        with tempfile.NamedTemporaryFile(delete=False) as temp_audio:
            await file.download_to_drive(temp_audio.name)
            
            # Converti in WAV con la funzione generica
            wav_path = convert_audio_to_wav(temp_audio.name)
            
            # Elabora l'audio (trascrive o riassume in base alla lunghezza)
            # result_text = transcribe_audio_chunks(wav_path)
            result_text = await transcribe_audio_chunks_async(wav_path)
            
            # Elimina i file temporanei
            try:
                os.unlink(temp_audio.name)
                os.unlink(wav_path)
            except:
                pass
            
            # Se non c'è nessun risultato
            if not result_text or not result_text.strip():
                await processing_message.edit_text("Non sono riuscito a trascrivere l'audio.")
                return
            
            # Dividi il risultato in messaggi più piccoli se necessario
            text_parts = split_text_for_telegram(result_text)
            
            # # # Invia i messaggi
            # await processing_message.delete()
            
            # Prepara l'intestazione in base al tipo di elaborazione
            header = "📝 **Trascrizione:**\n\n"
            
            # Invia il primo messaggio con l'intestazione
            await processing_message.edit_text(f"{header}{text_parts[0]}")
            
            # Invia i messaggi rimanenti (se presenti)
            for part in text_parts[1:]:
                await update.message.reply_text(part)
            
            # Invia riassunti se il primo messaggio è più lungo di 2000 caratteri
            if len(text_parts[0]) > 2000:
                await update.message.reply_text("Le trascrizioni sono lunghe, invio i riassunti...")
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    chunk_summaries = list(executor.map(summarize_transcription, text_parts))
                for i, summary in enumerate(chunk_summaries):
                    if summary:
                        await update.message.reply_text(f"Riassunto {i+1}:\n{summary}")
                    else:
                        await update.message.reply_text(f"Riassunto {i+1} non disponibile.")

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
    app.add_handler(MessageHandler(filters.AUDIO, handle_voice))

    logger.info("Bot avviato...")
    app.run_polling()

if __name__ == "__main__":
    main()
