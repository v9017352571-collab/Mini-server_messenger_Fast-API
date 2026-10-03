import socketio, database
from fastapi import FastAPI

# 1. Создаем асинхронный SocketIO сервер
# async_mode='asgi' позволяет ему работать в одном event loop с FastAPI
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")

# 2. Создаем основное FastAPI приложение
app = FastAPI(
    title="YourTurn Async Server",
    description="Backend for board game Tinder with E2EE",
    version="1.0.0"
)

# 3. Монтируем SocketIO в FastAPI по пути /socket.io
# Клиент python-socketio по умолчанию стучится именно на этот путь
app.mount("/socket.io", socketio.ASGIApp(sio))

# --- Демонстрация того, что REST и WebSocket живут вместе ---
@app.get("/", tags=["System"])
async def root():
    return {"message": "YourTurn Async Server is running!"}

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "active_rooms": len(database.rooms_metadata)}

# Импортируем database, чтобы использовать в роуте выше
from database import rooms_metadata