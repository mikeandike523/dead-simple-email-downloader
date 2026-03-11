import os


def auth_file(provider: str) -> str:
    return os.path.join(".dsed", "auth", f"{provider}.json")


def index_root(provider: str, product: str) -> str:
    return os.path.join(".dsed", "indices", provider, product)


def cache_root(provider: str, product: str) -> str:
    return os.path.join(".dsed", "caches", provider, product)


def debug_root() -> str:
    return os.path.join(".dsed", "debug")
