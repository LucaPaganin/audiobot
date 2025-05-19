import os
from pathlib import Path
import tempfile, uuid
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts import SYSTEM_PROMPT, SUMMARY_PROMPT
from langchain_core.output_parsers import StrOutputParser
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import requests
import time
import wave
import contextlib
import concurrent.futures
from typing import List, Tuple, Dict
from logging_config import setup_logger

# Configurazione del logger
logger = setup_logger(__name__)

# Config Gemini (qui usiamo ChatOpenAI come placeholder)
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    max_tokens=2000,
    timeout=None,
    max_retries=2,
    # other params...
)

summary_prompt = PromptTemplate.from_template(
    SUMMARY_PROMPT
)
summary_chain = summary_prompt | llm | StrOutputParser()

# Config Azure Speech
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

# Costanti per la gestione dell'audio
CHUNK_DURATION_MS = 60 * 1000  # 60 secondi per chunk
OVERLAP_DURATION_MS = 3 * 1000  # 3 secondi di sovrapposizione
MAX_TELEGRAM_MESSAGE_LENGTH = 4096  # Massimo caratteri per messaggio Telegram
LONG_AUDIO_THRESHOLD_MS = 90 * 1000  # 1 minuto e 30 secondi


def get_wav_duration(file_path: str) -> float:
    logger.debug(f"Ottenimento della durata del file WAV: {file_path}")
    with contextlib.closing(wave.open(file_path, 'rb')) as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration = frames / float(rate)
        logger.debug(f"Durata del file WAV: {duration:.2f} secondi")
        return duration


def convert_ogg_to_wav(ogg_path: str) -> str:
    """Converte un file .ogg in .wav e restituisce il path temporaneo WAV."""
    try:
        logger.info(f"Convertendo file OGG in WAV: {ogg_path}")
        audio = AudioSegment.from_file(ogg_path, format="ogg")
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio.export(temp_wav.name, format="wav")
        logger.info(f"Conversione completata: {temp_wav.name}")
        return temp_wav.name
    except Exception as e:
        logger.error(f"Errore durante la conversione da ogg a wav: {e}", exc_info=True)
        raise RuntimeError(f"Errore durante la conversione da ogg a wav: {e}")


def split_audio_file(audio_path: str) -> List[str]:
    """
    Divide un file audio in chunk con sovrapposizione.
    
    Args:
        audio_path: Percorso del file audio da dividere
        
    Returns:
        Lista di percorsi ai file audio temporanei
    """
    try:
        logger.info(f"Dividendo il file audio in chunk: {audio_path}")
        # Carica l'audio
        audio = AudioSegment.from_file(audio_path)
        
        # Lunghezza totale dell'audio in millisecondi
        total_duration = len(audio)
        logger.info(f"Durata totale dell'audio: {total_duration/1000:.2f} secondi")
        
        chunk_files = []
        
        # Se l'audio è più corto della dimensione di un chunk, lo restituiamo così com'è
        if total_duration <= CHUNK_DURATION_MS:
            logger.info("Audio più corto della dimensione di un chunk, non diviso")
            return [audio_path]
        
        # Altrimenti lo dividiamo in chunk con sovrapposizione
        for start_ms in range(0, total_duration, CHUNK_DURATION_MS - OVERLAP_DURATION_MS):
            # Calcola l'inizio e la fine del chunk
            end_ms = min(start_ms + CHUNK_DURATION_MS, total_duration)
            chunk_duration = (end_ms - start_ms) / 1000
            
            logger.info(f"Creazione chunk {len(chunk_files)+1}: {start_ms/1000:.1f}s - {end_ms/1000:.1f}s ({chunk_duration:.1f}s)")
            
            # Estrai il chunk
            chunk = audio[start_ms:end_ms]
            
            # Salva il chunk in un file temporaneo
            temp_chunk = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            chunk.export(temp_chunk.name, format="wav")
            chunk_files.append(temp_chunk.name)
            
            # Se siamo arrivati alla fine dell'audio, usciamo dal ciclo
            if end_ms >= total_duration:
                break
        
        logger.info(f"Creati {len(chunk_files)} chunk audio")
        return chunk_files
    except Exception as e:
        logger.error(f"Errore durante la divisione dell'audio: {e}", exc_info=True)
        raise RuntimeError(f"Errore durante la divisione dell'audio: {e}")


# Funzione per trascrivere con Azure Speech
def transcribe_audio_azure(file_path: str) -> str:
    logger.info(f"Iniziata trascrizione Azure Speech per il file: {file_path}")
    
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_recognition_language = "it-IT"
    # Abilita punteggiatura automatica
    speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_PostProcessingOption, "TrueText")
    
    file_path = Path(file_path)
    if file_path.suffix == ".ogg":
        logger.info(f"Convertendo file OGG in WAV: {file_path}")
        file_path = convert_ogg_to_wav(file_path)
    elif file_path.suffix != ".wav":
        logger.error(f"Formato file non supportato: {file_path.suffix}")
        raise ValueError("Il file audio deve essere in formato .wav o .ogg.")
    if not file_path.is_file():
        logger.error(f"File non trovato: {file_path}")
        raise FileNotFoundError(f"File non trovato: {file_path}")
    
    logger.info(f"Configurazione Azure Speech per riconoscimento")
    audio_config = speechsdk.AudioConfig(filename=str(file_path))
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    logger.info("Avvio riconoscimento vocale con Azure")
    result = recognizer.recognize_once()
    
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        text_len = len(result.text)
        logger.info(f"Trascrizione completata con successo: {text_len} caratteri")
        return result.text
    else:
        logger.warning(f"Trascrizione fallita: {result.reason}")
        return "Errore nella trascrizione o audio non riconosciuto."


def transcribe_chunk(chunk_path: str) -> str:
    """
    Funzione per trascrivere un singolo chunk audio.
    Da usare con ThreadPoolExecutor.
    """
    logger.debug(f"Iniziata trascrizione del chunk: {chunk_path}")
    result = transcribe_audio_azure(chunk_path)
    logger.debug(f"Terminata trascrizione del chunk: {chunk_path}")
    return result


def transcribe_audio_chunks(audio_path: str) -> Tuple[str, bool]:
    """
    Trascrive un file audio dividendolo in chunk e processandoli in parallelo.
    
    Args:
        audio_path: Percorso del file audio da trascrivere
        
    Returns:
        Tuple[str, bool]: (Testo trascritto o riassunto, flag che indica se è un riassunto)
    """
    logger.info(f"Inizio elaborazione audio: {audio_path}")
    
    # Converti OGG in WAV se necessario
    file_path = Path(audio_path)
    if file_path.suffix == ".ogg":
        audio_path = convert_ogg_to_wav(audio_path)
        
    # Ottieni la durata dell'audio
    duration_ms = get_wav_duration(audio_path) * 1000
    logger.info(f"Durata audio: {duration_ms/1000:.2f} secondi")
    
    # Dividi l'audio in chunk solo se è più lungo della soglia
    if duration_ms > CHUNK_DURATION_MS:
        logger.info("Audio più lungo della soglia di chunking, dividendo in parti...")
        chunks = split_audio_file(audio_path)
    else:
        logger.info("Audio più corto della soglia di chunking, elaborando come singolo file")
        chunks = [audio_path]
        
    # Trascrivi tutti i chunk in parallelo usando ThreadPoolExecutor
    logger.info(f"Inizio trascrizione di {len(chunks)} chunk audio in parallelo")
    transcriptions = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        transcriptions = list(executor.map(transcribe_chunk, chunks))
    logger.info("Trascrizione di tutti i chunk completata")
    
    # Se l'audio è più lungo della soglia per il riassunto, crea riassunti separati per ogni chunk
    is_summary = False
    if duration_ms > LONG_AUDIO_THRESHOLD_MS:
        logger.info(f"Audio più lungo di {LONG_AUDIO_THRESHOLD_MS/1000:.1f}s, creando riassunti...")
        is_summary = True
        # Processa i riassunti di ogni chunk in parallelo
        with concurrent.futures.ThreadPoolExecutor() as executor:
            chunk_summaries = list(executor.map(summarize_transcription, transcriptions))
        
        # Unisci i riassunti dei chunk
        result = " ".join(chunk_summaries)
        logger.info(f"Riassunto completato: {len(result)} caratteri")
    else:
        # Unisci le trascrizioni senza riassumere
        result = " ".join(transcriptions)
        logger.info(f"Trascrizione completata: {len(result)} caratteri")
        
    # Pulisci i file temporanei (tranne l'originale)
    if len(chunks) > 1:
        logger.info("Pulizia dei file temporanei...")
        for chunk in chunks:
            try:
                os.unlink(chunk)
            except Exception as e:
                logger.warning(f"Impossibile eliminare il file temporaneo {chunk}: {e}")
                
    return result, is_summary


def summarize_transcription(transcription: str) -> str:
    logger.debug(f"Iniziata sintesi di un testo di {len(transcription)} caratteri")
    summary = summary_chain.invoke({"transcription": transcription})
    logger.debug(f"Terminata sintesi: prodotti {len(summary)} caratteri")
    return summary


def split_text_for_telegram(text: str) -> List[str]:
    """
    Divide il testo in parti che non superano il limite massimo di caratteri di Telegram.
    
    Args:
        text: Testo da dividere
        
    Returns:
        Lista di stringhe, ciascuna non più lunga di MAX_TELEGRAM_MESSAGE_LENGTH
    """
    logger.info(f"Dividendo il testo per Telegram: {len(text)} caratteri totali")
    if len(text) <= MAX_TELEGRAM_MESSAGE_LENGTH:
        logger.info("Testo più corto del limite di Telegram, non è necessario dividerlo")
        return [text]
        
    parts = []
    
    # Dividi per paragrafi se possibile
    paragraphs = text.split("\n\n")
    current_part = ""
    
    for paragraph in paragraphs:
        # Se questo paragrafo da solo è già troppo grande, dividi ulteriormente
        if len(paragraph) > MAX_TELEGRAM_MESSAGE_LENGTH:
            # Se abbiamo già del testo nella parte corrente, aggiungiamolo
            if current_part:
                parts.append(current_part)
                current_part = ""
                
            # Dividi questo paragrafo in parti più piccole (per frasi)
            sentences = paragraph.replace(". ", ".\n").split("\n")
            sub_part = ""
            
            for sentence in sentences:
                if len(sub_part) + len(sentence) + 1 <= MAX_TELEGRAM_MESSAGE_LENGTH:
                    sub_part += sentence + " "
                else:
                    if sub_part:
                        parts.append(sub_part.strip())
                    sub_part = sentence + " "
            
            if sub_part:
                parts.append(sub_part.strip())
        else:
            # Controlliamo se possiamo aggiungere questo paragrafo alla parte corrente
            if len(current_part) + len(paragraph) + 2 <= MAX_TELEGRAM_MESSAGE_LENGTH:
                current_part += (paragraph + "\n\n")
            else:
                if current_part:
                    parts.append(current_part.strip())
                current_part = paragraph + "\n\n"
    
    # Aggiungi l'ultima parte se necessario
    if current_part:
        parts.append(current_part.strip())
        
    logger.info(f"Testo diviso in {len(parts)} parti per Telegram")
    return parts

