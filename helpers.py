import os
import tempfile
from pydub import AudioSegment
import azure.cognitiveservices.speech as speechsdk
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from prompts import SYSTEM_PROMPT, SUMMARY_PROMPT
from langchain_core.output_parsers import StrOutputParser

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
def transcribe_audio(file_path: str) -> str:
    speech_config = speechsdk.SpeechConfig(subscription=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    speech_config.speech_recognition_language = "it-IT"
    # Abilita punteggiatura automatica
    speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_PostProcessingOption, "TrueText")
    
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