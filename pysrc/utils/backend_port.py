import os

_RUNTIME_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "runtime",
    "next_port.txt",
)


def get_backend_port() -> int:
    """
    Return the port the Next.js backend is listening on.
    Reads ./runtime/next_port.txt written by `dsed backend start`.
    Falls back to 3000 silently so `pnpm dev` workflows still work.
    """
    try:
        with open(_RUNTIME_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 3000
