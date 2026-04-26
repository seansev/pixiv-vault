import os

def confirm(msg: str) -> bool:
    try:
        res = input(f"{msg} [Y/n] ").strip().lower()
    except EOFError:
        return False
    return res not in ('n', 'no')

def parse_bool(text: str, default: bool = False):
    val = text.strip().lower()
    if val in ('true', 't', 'yes', 'y', 'on', '1'):
        return True
    if val in ('false', 'f', 'no', 'n', 'off', '0'):
        return False
    return default

def env_bool(key: str, default: bool = False):
    val = os.getenv(key, "").strip().lower()
    return parse_bool(val, default)
