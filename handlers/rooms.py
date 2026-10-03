from socketio_server import sio
from database import users_pub_keys, rooms_metadata
from datetime import datetime


@sio.event
async def join_group(sid, data):
    group_id = data['group_id']
    user_id = data['user_id']

    # Подключаем SID клиента к комнате группы
    await sio.enter_room(sid, group_id)

    if group_id not in rooms_metadata:
        rooms_metadata[group_id] = {'members': [], 'last_activity': datetime.now()}

    existing_members = rooms_metadata[group_id]['members'].copy()
    rooms_metadata[group_id]['members'].append(user_id)
    rooms_metadata[group_id]['last_activity'] = datetime.now()

    new_user_pub_key = users_pub_keys.get(user_id)
    print(f"[SERVER] ✅ {user_id} вошел в группу '{group_id}'")

    # 1. Системное сообщение всем в комнате
    await sio.emit('system_message', {'text': f"{user_id} присоединился к чату"}, room=group_id)

    # 2. Лично старым участникам: "Пришел новый, вот его ключ"
    for member in existing_members:
        await sio.emit('new_member_joined', {
            'new_user_id': user_id,
            'new_user_pub_key': new_user_pub_key
        }, room=member)  # room=member работает, т.к. при register_user мы сделали enter_room(sid, user_id)

    # 3. Лично новому участнику: "Вот список всех, кто тут уже есть"
    existing_members_info = {
        member: users_pub_keys[member]
        for member in existing_members if member in users_pub_keys
    }

    await sio.emit('existing_members_info', {
        'group_id': group_id,
        'members': existing_members_info
    }, room=user_id)


@sio.event
async def leave_group(sid, data):
    group_id = data['group_id']
    user_id = data['user_id']

    await sio.leave_room(sid, group_id)

    if group_id in rooms_metadata:
        if user_id in rooms_metadata[group_id]['members']:
            rooms_metadata[group_id]['members'].remove(user_id)
        rooms_metadata[group_id]['last_activity'] = datetime.now()

    print(f"[SERVER] 🚪 {user_id} вышел из '{group_id}'")

    await sio.emit('system_message', {'text': f"{user_id} покинул чат"}, room=group_id)
    # Уведомляем оставшихся о необходимости смены ключей (Forward Secrecy)
    await sio.emit('member_left', {'group_id': group_id, 'user_id': user_id}, room=group_id)
