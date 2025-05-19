# AudioBot - Telegram Bot for Audio Transcription and Summarization

AudioBot è un bot Telegram che trascrive messaggi audio di qualsiasi lunghezza e crea riassunti intelligenti per audio lunghi.

## Caratteristiche Principali

- **Trascrizione audio con Azure AI Speech**: Converte i messaggi vocali in testo con alta precisione
- **Elaborazione audio di qualsiasi lunghezza**: Divide gli audio lunghi in chunk e li processa in parallelo
- **Riassunti intelligenti per audio lunghi**: Per audio più lunghi di 1 minuto e 30 secondi, genera un riassunto invece della trascrizione completa
- **Gestione messaggi multipli**: Divide automaticamente i risultati lunghi in più messaggi per rispettare i limiti di Telegram
- **Sistema di logging completo**: Registra tutte le operazioni in file di log rotanti per facilitare debug e monitoraggio

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

### Logging

Il sistema utilizza un sistema di logging completo che registra tutte le operazioni nei seguenti modi:

- **Console**: Mostra i log in tempo reale durante l'esecuzione
- **File di log**: Salva i log nella directory `logs/` con rotazione automatica
  - I file sono nominati con il formato `audiobot_YYYYMMDD.log`
  - Ogni file può raggiungere una dimensione massima di 10 MB
  - Vengono mantenuti fino a 5 file di backup

Per visualizzare i log salvati:

```bash
cat logs/audiobot_*.log
```

Per seguire i log in tempo reale durante l'esecuzione:

```bash
tail -f logs/audiobot_*.log
```

## Dettagli Tecnici

### Architettura

- **Trascrizione Audio**: Utilizza Azure AI Speech per convertire il parlato in testo
- **Elaborazione Parallela**: Divide gli audio lunghi in chunk con sovrapposizione di 3 secondi per garantire continuità
- **Riassunti**: Utilizza Gemini LLM via LangChain per generare riassunti di audio lunghi
- **Gestione Messaggi**: Divide automaticamente i risultati lunghi in più messaggi rispettando il limite di 4096 caratteri di Telegram
- **Sistema di Logging**: Implementa logging strutturato per tutte le operazioni con supporto per file e console

### File Principali

- `bot.py`: Implementazione del bot Telegram
- `helpers.py`: Funzioni di utilità per elaborazione audio, trascrizione e riassunti
- `prompts.py`: Prompt utilizzati per il riassunto con Gemini LLM
- `debug_audio.py`: Script per testing delle funzionalità di elaborazione audio
- `logging_config.py`: Configurazione centralizzata del sistema di logging

## Note di Implementazione

- Il sistema usa ThreadPoolExecutor per processare i chunk audio in parallelo
- La sovrapposizione di 3 secondi tra chunk garantisce continuità nella trascrizione
- I file temporanei vengono eliminati automaticamente dopo l'uso
- Per audio lunghi (>90s), viene generato un riassunto per ogni chunk e poi uniti in un riassunto completo
- I log forniscono informazioni dettagliate su ogni fase di elaborazione, inclusi tempi e dimensioni
- La rotazione dei file di log garantisce che lo spazio disco non venga saturato
