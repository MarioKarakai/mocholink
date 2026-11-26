import secrets
import string

ALIAS_ALPHABET: str = string.ascii_letters + string.digits


def generate_random_alias(length: int = 7) -> str:
    if length <= 0:
        raise ValueError("length debe ser mayor que 0")
    return "".join(secrets.choice(ALIAS_ALPHABET) for _ in range(length))
