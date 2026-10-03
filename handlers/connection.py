from socketio_server import sio
from database import users_pub_keys


@sio.event
async def connect(sid, environ):
    """Клиент только что установил TCP/WebSocket соединение"""
    print(f"[SERVER] 🔌 Клиент подключился. SID: {sid}")


@sio.event
async def disconnect(sid):
    """Клиент отключился"""
    print(f"[SERVER] 🔌 Клиент отключился. SID: {sid}")


@sio.event
async def register_user(sid, data):
    """Клиент отправил свой публичный ключ и ID"""
    user_id = data['user_id']
    pub_key = data['pub_key']

    # Сохраняем ключ
    users_pub_keys[user_id] = pub_key

    # КРИТИЧЕСКИ ВАЖНО: Создаем "личную комнату" с именем user_id.
    # Это нужно, чтобы мы могли слать сообщения лично этому юзеру (room=user_id)
    await sio.enter_room(sid, user_id)

    print(f"[SERVER] 📝 Зарегистрирован: {user_id} (SID: {sid})")