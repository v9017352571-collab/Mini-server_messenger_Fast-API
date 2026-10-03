import uvicorn
from config import HOST, PORT

# Импортируем app из ядра
from socketio_server import app

# ВАЖНО: Импортируем хендлеры, чтобы декораторы @sio.event зарегистрировались!
import handlers.connection
import handlers.rooms
import handlers.messaging

if __name__ == "__main__":
    print(f"🚀 [SERVER] Запуск асинхронного FastAPI + SocketIO сервера на {HOST}:{PORT}...")
    # uvicorn.run - это асинхронный веб-сервер, который идеально подходит для FastAPI
    uvicorn.run(app, host=HOST, port=PORT)
