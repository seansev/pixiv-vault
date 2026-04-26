import os

def confirm(msg: str) -> bool:
    try:
        res = input(f"{msg} [Y/n] ").strip().lower()
    except EOFError:
        return False
    return res not in ('n', 'no')
