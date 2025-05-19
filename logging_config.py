#!/usr/bin/env python3
"""
Configurazione centralizzata del logging per l'applicazione AudioBot.
"""

import os
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import datetime

# Importa colorlog se disponibile, altrimenti usa logging standard
try:
    import colorlog
    has_colorlog = True
except ImportError:
    has_colorlog = False

# Creazione della directory dei log se non esiste
LOG_DIR = Path("logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Formato del timestamp per i file di log
timestamp = datetime.datetime.now().strftime("%Y%m%d")
log_file = LOG_DIR / f"audiobot_{timestamp}.log"

# Configurazione del formato dei log
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configurazione handler per console con colori se disponibile
console_handler = logging.StreamHandler(sys.stdout)
if has_colorlog:
    color_formatter = colorlog.ColoredFormatter(
        "%(log_color)s" + LOG_FORMAT,
        datefmt=DATE_FORMAT,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(color_formatter)
else:
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

# Configurazione handler per file con rotazione
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))


def setup_logger(name=None):
    """
    Configura e restituisce un logger con il nome specificato.
    
    Args:
        name: Nome del logger, se None viene utilizzato il nome del file chiamante
        
    Returns:
        Logger configurato
    """
    # Se il nome non è specificato, utilizziamo il nome del modulo chiamante
    if name is None:
        import inspect
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        if mod is not None:
            name = mod.__name__
        else:
            name = Path(frm[1]).stem
    
    # Ottieni il logger
    logger = logging.getLogger(name)
    
    # Imposta il livello di log
    logger.setLevel(logging.INFO)
    
    # Aggiungi gli handler se non sono già presenti
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
    
    # Disattiva la propagazione ai logger parent
    logger.propagate = False
    
    return logger


# Logger di default per l'applicazione
app_logger = setup_logger("audiobot")
