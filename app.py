import asyncio
from contextlib import asynccontextmanager
import threading
import time
from fastapi import FastAPI
import uvicorn
from logging_config import setup_logger
from bot import bot_app


# Configurazione del logger
logger = setup_logger(__name__)

def run_bot_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        bot_app.run_polling(stop_signals=None)  # blocca finché il bot è attivo
    finally:
        loop.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_thread = threading.Thread(target=run_bot_in_thread, name="bot-thread", daemon=True)
    bot_thread.start()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    # Avvia FastAPI (serve per mantenere vivo il container)
    uvicorn.run(app, host="0.0.0.0", port=8000)
