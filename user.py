import base64
import socketio
import time
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet

sio = socketio.Client()
SERVER_URL = "http://127.0.0.1:5000"

USER_ID = ""
GROUP_ID = ""

# --- Криптография ---
my_1on1_priv = x25519.X25519PrivateKey.generate()
my_1on1_pub = my_1on1_priv.public_key()
my_1on1_pub_bytes = my_1on1_pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

# ИСПРАВЛЕНИЕ: Храним сырой ключ и объект Fernet отдельно
my_group_raw_keys = {}  # { "group_id": bytes (32 байта) }
my_group_fernets = {}  # { "group_id": Fernet_object }
group_peers_sender_keys = {}  # { "group_id": { "user_id": Fernet_object } }
users_pub_keys = {}  # { "user_id": "base64_pub_key" }


def encrypt_and_send_my_key(target_user_id, group_id):
    """Шифрует мой сырой Sender Key публичным ключом цели и отправляет ему"""
    target_pub_key_b64 = users_pub_keys.get(target_user_id)
    if not target_pub_key_b64:
        print(f"❌ [{USER_ID}] Нет публичного ключа для {target_user_id}")
        return

    try:
        eph_priv = x25519.X25519PrivateKey.generate()
        eph_pub = eph_priv.public_key()

        peer_pub_bytes = base64.b64decode(target_pub_key_b64)
        peer_pub_key = x25519.X25519PublicKey.from_public_bytes(peer_pub_bytes)

        shared_secret = eph_priv.exchange(peer_pub_key)
        hkdf = HKDFExpand(algorithm=hashes.SHA256(), length=32, info=b"group-setup")
        wrap_key = base64.urlsafe_b64encode(hkdf.derive(shared_secret))

        temp_fernet = Fernet(wrap_key)

        # ИСПРАВЛЕНИЕ: Берем сырой ключ из правильного словаря
        raw_key = my_group_raw_keys[group_id]
        encrypted_my_key = temp_fernet.encrypt(raw_key)

        sio.emit('send_my_sender_key', {
            'target_user': target_user_id,
            'sender_id': USER_ID,
            'group_id': group_id,
            'eph_pub': base64.b64encode(
                eph_pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode(),
            'enc_key': base64.b64encode(encrypted_my_key).decode()
        })
        print(f"🔑 [{USER_ID}] Отправил мой ключ для {target_user_id} в группе '{group_id}'")
    except Exception as e:
        print(f"❌ [{USER_ID}] Ошибка отправки ключа: {e}")


def join_new_group(group_id):
    global GROUP_ID
    GROUP_ID = group_id

    # ИСПРАВЛЕНИЕ: Генерируем и сохраняем сырой ключ отдельно
    raw_key = Fernet.generate_key()
    my_group_raw_keys[GROUP_ID] = raw_key
    my_group_fernets[GROUP_ID] = Fernet(raw_key)
    group_peers_sender_keys[GROUP_ID] = {}

    sio.emit('join_group', {'group_id': GROUP_ID, 'user_id': USER_ID})
    print(f"✅ [{USER_ID}] Вошел в группу '{GROUP_ID}' с новым ключом шифрования.")


def leave_current_group():
    global GROUP_ID
    if not GROUP_ID:
        return

    sio.emit('leave_group', {'group_id': GROUP_ID, 'user_id': USER_ID})

    # Уничтожаем ключи этой группы локально (Forward Secrecy)
    my_group_raw_keys.pop(GROUP_ID, None)
    my_group_fernets.pop(GROUP_ID, None)
    group_peers_sender_keys.pop(GROUP_ID, None)
    print(f"🚪 [{USER_ID}] Вышел из '{GROUP_ID}'. Локальные ключи уничтожены.")
    GROUP_ID = ""


# --- Обработчики событий ---

@sio.on('connect')
def on_connect():
    sio.emit('register_user', {
        'user_id': USER_ID,
        'pub_key': base64.b64encode(my_1on1_pub_bytes).decode()
    })


@sio.on('new_member_joined')
def on_new_member_joined(data):
    new_user_id = data['new_user_id']
    users_pub_keys[new_user_id] = data['new_user_pub_key']
    print(f"\n🔑 [{USER_ID}] {new_user_id} присоединился. Отправляю ему мой ключ...")
    encrypt_and_send_my_key(new_user_id, GROUP_ID)


@sio.on('existing_members_info')
def on_existing_members_info(data):
    group_id = data['group_id']
    members = data['members']

    print(f"\n🔑 [{USER_ID}] Вижу участников в '{group_id}': {list(members.keys())}. Отправляю им мой ключ...")
    for other_user_id, other_pub_key in members.items():
        users_pub_keys[other_user_id] = other_pub_key
        encrypt_and_send_my_key(other_user_id, group_id)


@sio.on('member_left')
def on_member_left(data):
    group_id = data['group_id']
    left_user = data['user_id']

    if group_id in group_peers_sender_keys:
        # 1. Удаляем ключ ушедшего участника
        group_peers_sender_keys[group_id].pop(left_user, None)

        # 2. Если это ушел не мы, мы МЕНЯЕМ свой ключ и рассылаем новый оставшимся!
        if left_user != USER_ID and group_id == GROUP_ID:
            print(f"\n🔄 [{USER_ID}] {left_user} вышел. Генерирую НОВЫЙ ключ для безопасности...")

            # ИСПРАВЛЕНИЕ: Обновляем и сырой ключ, и объект Fernet
            new_raw_key = Fernet.generate_key()
            my_group_raw_keys[group_id] = new_raw_key
            my_group_fernets[group_id] = Fernet(new_raw_key)

            # Рассылаем новый ключ всем, кто еще остался в словаре
            for target_user in list(group_peers_sender_keys[group_id].keys()):
                encrypt_and_send_my_key(target_user, group_id)
            print(f"✅ [{USER_ID}] Ключ обновлен и разослан оставшимся участникам.")


@sio.on('receive_sender_key')
def on_receive_sender_key(data):
    sender_id = data['sender_id']
    group_id = data['group_id']
    eph_pub_b64 = data['eph_pub']
    enc_key_b64 = data['enc_key']

    try:
        eph_pub_bytes = base64.b64decode(eph_pub_b64)
        eph_pub_key = x25519.X25519PublicKey.from_public_bytes(eph_pub_bytes)

        shared_secret = my_1on1_priv.exchange(eph_pub_key)
        hkdf = HKDFExpand(algorithm=hashes.SHA256(), length=32, info=b"group-setup")
        wrap_key = base64.urlsafe_b64encode(hkdf.derive(shared_secret))

        temp_fernet = Fernet(wrap_key)
        raw_peer_key = temp_fernet.decrypt(base64.b64decode(enc_key_b64))

        if group_id not in group_peers_sender_keys:
            group_peers_sender_keys[group_id] = {}

        group_peers_sender_keys[group_id][sender_id] = Fernet(raw_peer_key)
        print(f"✅ [{USER_ID}] Успешно получен ключ от {sender_id} для группы '{group_id}'")
    except Exception as e:
        print(f"❌ [{USER_ID}] Ошибка расшифровки ключа от {sender_id}: {e}")


@sio.on('new_message')
def on_new_message(data):
    group_id = data['group_id']
    sender = data['sender_id']
    encrypted_payload = data['payload']

    if sender != USER_ID and group_id == GROUP_ID:
        sender_fernet = group_peers_sender_keys.get(group_id, {}).get(sender)
        if sender_fernet:
            try:
                decrypted_text = sender_fernet.decrypt(encrypted_payload.encode()).decode()
                print(f"\n📩 [{USER_ID}] Новое от {sender}: {decrypted_text}")
                print(f"[{USER_ID}] > ", end="", flush=True)
            except Exception:
                print(f"\n❌ [{USER_ID}] Ошибка расшифровки сообщения от {sender}")
                print(f"[{USER_ID}] > ", end="", flush=True)
        else:
            print(f"\n⏳ [{USER_ID}] Сообщение от {sender}, но ключ еще не получен.")
            print(f"[{USER_ID}] > ", end="", flush=True)


@sio.on('system_message')
def on_system_message(data):
    print(f"\n⚙️  {data['text']}")
    print(f"[{USER_ID}] > ", end="", flush=True)


# --- Главный цикл ---
def main():
    global USER_ID, GROUP_ID

    USER_ID = input("👤 Введите ваше имя: ").strip()
    if not USER_ID:
        USER_ID = "User"

    print(f"🔌 [{USER_ID}] Подключаюсь к серверу...")
    sio.connect(SERVER_URL)
    time.sleep(0.5)  # Даем время на регистрацию

    GROUP_ID = input("💬 Введите название группы для входа: ").strip()
    if not GROUP_ID:
        GROUP_ID = "general"

    join_new_group(GROUP_ID)

    print(f"\n💡 Команды: /leave (выйти), /join <группа> (войти в другую), /quit (выход)")

    try:
        while True:
            message = input(f"[{USER_ID}] > ").strip()

            if message == '/leave':
                leave_current_group()
            elif message.startswith('/join '):
                parts = message.split(' ', 1)
                if len(parts) == 2:
                    if GROUP_ID:
                        leave_current_group()  # Автоматический выход из старой группы
                    join_new_group(parts[1])
                else:
                    print("❌ Использование: /join <название_группы>")
            elif message == '/quit':
                if GROUP_ID:
                    leave_current_group()
                sio.disconnect()
                break
            elif message:
                if not GROUP_ID or GROUP_ID not in my_group_fernets:
                    print("❌ Вы не в группе! Используйте /join <группа>")
                    continue

                # ИСПРАВЛЕНИЕ: Используем правильный словарь для шифрования
                encrypted_payload = my_group_fernets[GROUP_ID].encrypt(message.encode()).decode()
                sio.emit('send_message', {
                    'group_id': GROUP_ID,
                    'sender_id': USER_ID,
                    'payload': encrypted_payload
                })

    except KeyboardInterrupt:
        print(f"\n👋 [{USER_ID}] Выход...")
        if GROUP_ID:
            leave_current_group()
        sio.disconnect()


if __name__ == '__main__':
    main()