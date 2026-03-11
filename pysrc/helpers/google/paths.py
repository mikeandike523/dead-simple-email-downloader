from pysrc.helpers.paths import auth_file, index_root, cache_root, debug_root

__all__ = ["auth_file", "index_root", "cache_root", "debug_root",
           "GOOGLE_AUTH", "GOOGLE_GMAIL_INDEX", "GOOGLE_GMAIL_CACHE"]

# Convenience constants for google/gmail
GOOGLE_AUTH = auth_file("google")
GOOGLE_GMAIL_INDEX = index_root("google", "gmail")
GOOGLE_GMAIL_CACHE = cache_root("google", "gmail")
