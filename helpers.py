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
    
    
    audio_config = speechsdk.AudioConfig(filename=file_path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    result = recognizer.recognize_once()
    
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    else:
        return "Errore nella trascrizione o audio non riconosciuto."


def summarize_transcription(transcription: str) -> str:
    summary = summary_chain.invoke({"transcription": transcription})
    return summary


def upload_to_blob_with_sas(
    file_path: str,
    blob_name: str = None,
    expiry_minutes: int = 60
) -> str:
    """
    Upload a file to Azure Blob Storage and return a URL with SAS token.

    Parameters:
        file_path: Path to the local audio file.
        connection_string: Azure Blob Storage connection string.
        container_name: Name of the container.
        blob_name: Name of the blob (optional, defaults to file name).
        expiry_minutes: SAS token expiry duration.

    Returns:
        URL with SAS token for public access.
    """
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_STORAGE_CONTAINER_NAME:
        raise ValueError("Azure Storage connection string or container name not set in environment variables.")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    blob_name = blob_name or os.path.basename(file_path)

    blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service.get_container_client(AZURE_STORAGE_CONTAINER_NAME)

    # Create container if not exists
    if not container_client.exists():
        container_client.create_container()

    # Upload blob
    blob_client = container_client.get_blob_client(blob_name)
    with open(file_path, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)

    # Generate SAS token
    sas_token = generate_blob_sas(
        account_name=blob_service.account_name,
        container_name=AZURE_STORAGE_CONTAINER_NAME,
        blob_name=blob_name,
        account_key=blob_service.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=expiry_minutes)
    )

    blob_url = f"{blob_client.url}?{sas_token}"
    return blob_url


def transcribe_long_audio_with_rest(
    audio_url: str,
    language: str = "it-IT",
    output_file: str = "transcription.txt",
    display_name: str = "LongAudioTranscription"
) -> str:
    """
    Transcribe a long audio file using Azure Speech batch transcription (REST API).

    Parameters:
        audio_url (str): Public URL of the audio file with SAS token if needed.
        azure_key (str): Azure Speech resource key.
        azure_region (str): Azure region (e.g., 'westeurope').
        language (str): Locale of the audio, e.g., 'it-IT'.
        output_file (str): Path to save the transcription result.
        display_name (str): A display name for the transcription job.

    Returns:
        str: Transcription content or path to saved file.
    """
    
    # 1. Create transcription job
    endpoint = f"https://{AZURE_SPEECH_REGION}.api.cognitive.microsoft.com/speechtotext/v3.1/transcriptions"
    
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_SPEECH_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "displayName": display_name,
        "locale": language,
        "contentUrls": [audio_url],
        "properties": {
            "diarizationEnabled": True,
            "wordLevelTimestampsEnabled": True,
            "punctuationMode": "DictatedAndAutomatic",
            "profanityFilterMode": "Masked"
        }
    }

    response = requests.post(endpoint, headers=headers, json=body)
    if response.status_code != 202:
        raise Exception(f"Failed to create transcription: {response.status_code}\n{response.text}")

    transcription_url = response.headers["Location"]
    print(f"Transcription job created: {transcription_url}")

    # 2. Poll status
    print("Waiting for transcription to complete...")
    while True:
        status_resp = requests.get(transcription_url, headers=headers)
        status_data = status_resp.json()
        status = status_data["status"]
        print(f"Status: {status}")
        if status in ["Succeeded", "Failed"]:
            break
        time.sleep(10)

    if status == "Failed":
        raise Exception("Transcription failed.")

    # 3. Download results
    results_urls = status_data.get("resultsUrls", {})
    transcription_uri = results_urls.get("transcription")

    if not transcription_uri:
        raise Exception("No transcription URL found in results.")

    result_resp = requests.get(transcription_uri)
    result_text = result_resp.text

    if len(result_text) < 1000:
        return result_text
    else:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result_text)
        return f"Transcription too long, saved to {output_file}"
