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
    with contextlib.closing(wave.open(file_path, 'rb')) as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        duration = frames / float(rate)
        return duration


def convert_ogg_to_wav(ogg_path: str) -> str:
    """Converte un file .ogg in .wav e restituisce il path temporaneo WAV."""
    try:
        audio = AudioSegment.from_file(ogg_path, format="ogg")
        temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio.export(temp_wav.name, format="wav")
        return temp_wav.name
    except Exception as e:
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
        # Carica l'audio
        audio = AudioSegment.from_file(audio_path)
        
        # Lunghezza totale dell'audio in millisecondi
        total_duration = len(audio)
        
        chunk_files = []
        
        # Se l'audio è più corto della dimensione di un chunk, lo restituiamo così com'è
        if total_duration <= CHUNK_DURATION_MS:
            return [audio_path]
        
        # Altrimenti lo dividiamo in chunk con sovrapposizione
        for start_ms in range(0, total_duration, CHUNK_DURATION_MS - OVERLAP_DURATION_MS):
            # Calcola l'inizio e la fine del chunk
            end_ms = min(start_ms + CHUNK_DURATION_MS, total_duration)
            
            # Estrai il chunk
            chunk = audio[start_ms:end_ms]
            
            # Salva il chunk in un file temporaneo
            temp_chunk = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            chunk.export(temp_chunk.name, format="wav")
            chunk_files.append(temp_chunk.name)
            
            # Se siamo arrivati alla fine dell'audio, usciamo dal ciclo
            if end_ms >= total_duration:
                break
                
        return chunk_files
    except Exception as e:
        raise RuntimeError(f"Errore durante la divisione dell'audio: {e}")


# Funzione per trascrivere con Azure Speech
def transcribe_audio_azure(file_path: str) -> str:
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_recognition_language = "it-IT"
    # Abilita punteggiatura automatica
    speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_PostProcessingOption, "TrueText")
    
    file_path = Path(file_path)
    if file_path.suffix == ".ogg":
        file_path = convert_ogg_to_wav(file_path)
    elif file_path.suffix != ".wav":
        raise ValueError("Il file audio deve essere in formato .wav o .ogg.")
    if not file_path.is_file():
        raise FileNotFoundError(f"File non trovato: {file_path}")
    
    
    audio_config = speechsdk.AudioConfig(filename=str(file_path))
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = recognizer.recognize_once()
    
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    else:
        return "Errore nella trascrizione o audio non riconosciuto."


def transcribe_chunk(chunk_path: str) -> str:
    """
    Funzione per trascrivere un singolo chunk audio.
    Da usare con ThreadPoolExecutor.
    """
    return transcribe_audio_azure(chunk_path)


def transcribe_audio_chunks(audio_path: str) -> Tuple[str, bool]:
    """
    Trascrive un file audio dividendolo in chunk e processandoli in parallelo.
    
    Args:
        audio_path: Percorso del file audio da trascrivere
        
    Returns:
        Tuple[str, bool]: (Testo trascritto o riassunto, flag che indica se è un riassunto)
    """
    # Converti OGG in WAV se necessario
    file_path = Path(audio_path)
    if file_path.suffix == ".ogg":
        audio_path = convert_ogg_to_wav(audio_path)
        
    # Ottieni la durata dell'audio
    duration_ms = get_wav_duration(audio_path) * 1000
    
    # Dividi l'audio in chunk solo se è più lungo della soglia
    if duration_ms > CHUNK_DURATION_MS:
        chunks = split_audio_file(audio_path)
    else:
        chunks = [audio_path]
        
    # Trascrivi tutti i chunk in parallelo usando ThreadPoolExecutor
    transcriptions = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        transcriptions = list(executor.map(transcribe_chunk, chunks))
        
    # Unisci le trascrizioni
    full_transcription = " ".join(transcriptions)
    
    # Se l'audio è più lungo della soglia per il riassunto, genera un riassunto
    is_summary = False
    if duration_ms > LONG_AUDIO_THRESHOLD_MS:
        result = summarize_transcription(full_transcription)
        is_summary = True
    else:
        result = full_transcription
        
    # Pulisci i file temporanei (tranne l'originale)
    if len(chunks) > 1:
        for chunk in chunks:
            try:
                os.unlink(chunk)
            except:
                pass
                
    return result, is_summary


def summarize_transcription(transcription: str) -> str:
    summary = summary_chain.invoke({"transcription": transcription})
    return summary


def split_text_for_telegram(text: str) -> List[str]:
    """
    Divide il testo in parti che non superano il limite massimo di caratteri di Telegram.
    
    Args:
        text: Testo da dividere
        
    Returns:
        Lista di stringhe, ciascuna non più lunga di MAX_TELEGRAM_MESSAGE_LENGTH
    """
    if len(text) <= MAX_TELEGRAM_MESSAGE_LENGTH:
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
        
    return parts

