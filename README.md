# AudioBot - Telegram Bot for Audio Transcription and Summarization

AudioBot è un bot Telegram che trascrive messaggi audio di qualsiasi lunghezza e crea riassunti intelligenti per audio lunghi.

## Caratteristiche Principali

- **Trascrizione audio con Azure AI Speech**: Converte i messaggi vocali in testo con alta precisione
- **Elaborazione audio di qualsiasi lunghezza**: Divide gli audio lunghi in chunk e li processa in parallelo
- **Riassunti intelligenti per audio lunghi**: Per audio più lunghi di 1 minuto e 30 secondi, genera un riassunto invece della trascrizione completa
- **Gestione messaggi multipli**: Divide automaticamente i risultati lunghi in più messaggi per rispettare i limiti di Telegram

## Requisiti

- Python 3.8+
- Telegram Bot Token
- Azure Speech Services (chiave e regione)
- Google API Key (per Gemini LLM)

## Installazione

1. Clona il repository o scarica il codice
2. Installa le dipendenze:

```bash
pip install -r requirements.txt
```

3. Crea un file `.env` nella directory del progetto (usa example.env come modello):

```
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=your_azure_speech_region
GOOGLE_API_KEY=your_google_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

4. Installa ffmpeg se non è già presente (necessario per la conversione audio):

```bash
# Per Ubuntu/Debian
sudo apt install ffmpeg

# Per MacOS
brew install ffmpeg
```

## Utilizzo

### Avvio del bot

```bash
python bot.py
```

### Debug e test delle funzioni di elaborazione audio

Usa lo script di debug per testare la trascrizione di un file audio senza avviare il bot:

```bash
python debug_audio.py /percorso/del/tuo/file/audio.wav
```

## Dettagli Tecnici

### Architettura

- **Trascrizione Audio**: Utilizza Azure AI Speech per convertire il parlato in testo
- **Elaborazione Parallela**: Divide gli audio lunghi in chunk con sovrapposizione di 3 secondi per garantire continuità
- **Riassunti**: Utilizza Gemini LLM via LangChain per generare riassunti di audio lunghi
- **Gestione Messaggi**: Divide automaticamente i risultati lunghi in più messaggi rispettando il limite di 4096 caratteri di Telegram

### File Principali

- `bot.py`: Implementazione del bot Telegram
- `helpers.py`: Funzioni di utilità per elaborazione audio, trascrizione e riassunti
- `prompts.py`: Prompt utilizzati per il riassunto con Gemini LLM
- `debug_audio.py`: Script per testing delle funzionalità di elaborazione audio

## Note di Implementazione

- Il sistema usa ThreadPoolExecutor per processare i chunk audio in parallelo
- La sovrapposizione di 3 secondi tra chunk garantisce continuità nella trascrizione
- I file temporanei vengono eliminati automaticamente dopo l'uso
- Per audio lunghi (>90s), viene generato un riassunto invece della trascrizione completa
