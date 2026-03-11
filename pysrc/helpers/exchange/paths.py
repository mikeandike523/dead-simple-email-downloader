from pysrc.helpers.paths import auth_file, index_root, cache_root, debug_root

__all__ = ["auth_file", "index_root", "cache_root", "debug_root",
           "EXCHANGE_AUTH", "EXCHANGE_OUTLOOK_INDEX", "EXCHANGE_OUTLOOK_CACHE"]

# Convenience constants for exchange/outlook
EXCHANGE_AUTH = auth_file("exchange")
EXCHANGE_OUTLOOK_INDEX = index_root("exchange", "outlook")
EXCHANGE_OUTLOOK_CACHE = cache_root("exchange", "outlook")
