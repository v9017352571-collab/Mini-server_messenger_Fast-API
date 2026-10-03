from socketio_server import sio
from database import rooms_metadata
from datetime import datetime


@sio.event
async def send_message(sid, data):
    group_id = data['group_id']
    sender_id = data['sender_id']
    payload = data['payload']  # Уже зашифрованный Fernet payload

    if group_id in rooms_metadata:
        rooms_metadata[group_id]['last_activity'] = datetime.now()

    print(f"[SERVER] 💬 Сообщение от {sender_id} в '{group_id}'")

    # Ретранслируем зашифрованное сообщение всем в комнате
    await sio.emit('new_message', {
        "group_id": group_id,
        "sender_id": sender_id,
        "payload": payload
    }, room=group_id)


@sio.event
async def send_my_sender_key(sid, data):
    target_user = data['target_user']

    # Отправляем зашифрованный Sender Key лично целевому пользователю
    # (в его личную комнату, созданную при register_user)
    await sio.emit('receive_sender_key', data, room=target_user)
