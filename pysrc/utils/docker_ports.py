import os
import subprocess
import sys
from termcolor import colored

# Resolve project root: pysrc/utils/ → pysrc/ → project root
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
COMPOSE_FILE = os.path.join(PROJECT_ROOT, "database", "docker-compose.yml")


def _find_docker_compose_cmd() -> list[str]:
    """
    Return the docker compose command prefix to use.
    Tries `docker compose` first, then `docker-compose`.
    Exits hard if neither is available.
    """
    # Try `docker compose` (v2 plugin)
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
        )
        if result.returncode == 0:
            return ["docker", "compose"]
    except FileNotFoundError:
        pass

    # Try standalone `docker-compose` (v1)
    try:
        result = subprocess.run(
            ["docker-compose", "version"],
            capture_output=True,
        )
        if result.returncode == 0:
            return ["docker-compose"]
    except FileNotFoundError:
        pass

    print(colored(
        "Error: neither 'docker compose' nor 'docker-compose' was found on PATH. "
        "Please install Docker and ensure it is on your PATH.",
        "red",
    ), file=sys.stderr)
    sys.exit(1)


def get_compose_port(service: str, container_port: int) -> int:
    """
    Return the host port that Docker has mapped to `container_port` on `service`.
    Fails hard (red message + sys.exit) if anything goes wrong.
    """
    cmd_prefix = _find_docker_compose_cmd()
    cmd = cmd_prefix + ["-f", COMPOSE_FILE, "port", service, str(container_port)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        print(colored(
            f"Error: could not execute docker compose command: {' '.join(cmd)}",
            "red",
        ), file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(colored(
            f"Error: 'docker compose port {service} {container_port}' failed.\n"
            f"Is the container running?  (docker compose up -d)\n"
            + (f"Details: {stderr}" if stderr else ""),
            "red",
        ), file=sys.stderr)
        sys.exit(1)

    output = result.stdout.strip()
    if not output:
        print(colored(
            f"Error: no port mapping returned for {service}:{container_port}.\n"
            "The container may not be running or the port is not published.",
            "red",
        ), file=sys.stderr)
        sys.exit(1)

    # Output is either "0.0.0.0:PORT" or ":::PORT"
    try:
        port = int(output.rsplit(":", 1)[-1])
    except ValueError:
        print(colored(
            f"Error: could not parse port from docker output: {output!r}",
            "red",
        ), file=sys.stderr)
        sys.exit(1)

    return port
