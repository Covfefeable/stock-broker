from uuid import uuid4

from app import extensions

ONLINE_USERS_KEY = "online:users"
ONLINE_CONNECTION_KEY_PATTERN = "online:user:{user_id}:conn:*"
ONLINE_CONNECTION_KEY = "online:user:{user_id}:conn:{connection_id}"
ONLINE_CONNECTION_TTL_SECONDS = 90


def create_online_connection(user_id: int) -> str:
    connection_id = uuid4().hex
    refresh_online_connection(user_id, connection_id)
    return connection_id


def refresh_online_connection(user_id: int, connection_id: str) -> None:
    if extensions.redis_client is None:
        return
    key = ONLINE_CONNECTION_KEY.format(user_id=user_id, connection_id=connection_id)
    pipe = extensions.redis_client.pipeline()
    pipe.set(key, "1", ex=ONLINE_CONNECTION_TTL_SECONDS)
    pipe.sadd(ONLINE_USERS_KEY, str(user_id))
    pipe.execute()


def iter_online_user_ids() -> list[int]:
    if extensions.redis_client is None:
        return []

    result: list[int] = []
    for raw_user_id in extensions.redis_client.smembers(ONLINE_USERS_KEY):
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            extensions.redis_client.srem(ONLINE_USERS_KEY, raw_user_id)
            continue

        pattern = ONLINE_CONNECTION_KEY_PATTERN.format(user_id=user_id)
        if any(extensions.redis_client.scan_iter(match=pattern, count=20)):
            result.append(user_id)
        else:
            extensions.redis_client.srem(ONLINE_USERS_KEY, raw_user_id)
    return result
