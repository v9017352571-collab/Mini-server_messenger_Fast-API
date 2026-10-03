from datetime import datetime

# В реальном проекте здесь будут асинхронные запросы к БД (SQLAlchemy).
# Пока что мы используем словари, как в вашем оригинальном коде,
# но с типизацией (это стандарт для FastAPI).

# { "user_id": "base64_pub_key" }
users_pub_keys: dict[str, str] = {}

# { "group_id": {"members": ["user1", "user2"], "last_activity": datetime} }
rooms_metadata: dict[str, dict] = {}
