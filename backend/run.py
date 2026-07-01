"""Inicia o servidor da API.

Uso:
    python run.py
    python run.py --port 8001
    $env:PORT=8001; python run.py
"""

from __future__ import annotations

import argparse
import socket
import sys

import uvicorn

HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((HOST, port))
            return True
        except OSError:
            return False


def find_free_port(start: int = DEFAULT_PORT, attempts: int = 10) -> int:
    for port in range(start, start + attempts):
        if port_available(port):
            return port
    print(
        f"Erro: nenhuma porta livre entre {start} e {start + attempts - 1}.",
        file=sys.stderr,
    )
    sys.exit(1)


def who_uses_port(port: int) -> str | None:
    if sys.platform != "win32":
        return None
    import subprocess

    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                return parts[-1]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicia a API do simulador SHM")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Porta do servidor (padrão: {DEFAULT_PORT} ou próxima livre)",
    )
    args = parser.parse_args()

    if args.port is not None:
        if not port_available(args.port):
            pid = who_uses_port(args.port)
            hint = f" (PID {pid})" if pid else ""
            print(
                f"Erro: porta {args.port} já está em uso{hint}.",
                file=sys.stderr,
            )
            if pid:
                print(f"  Encerre com: Stop-Process -Id {pid} -Force", file=sys.stderr)
            sys.exit(1)
        port = args.port
    else:
        port = find_free_port()

    if port != DEFAULT_PORT:
        pid = who_uses_port(DEFAULT_PORT)
        extra = f" (PID {pid})" if pid else ""
        print(f"[!] Porta {DEFAULT_PORT} ocupada{extra}. Usando porta {port}.")
        print(f"    No frontend, crie frontend/.env com:")
        print(f"    VITE_API_PORT={port}")
        print()

    print(f"API:  http://{HOST}:{port}")
    print(f"Docs: http://{HOST}:{port}/docs")
    print()

    uvicorn.run("main:app", host=HOST, port=port, reload=True)


if __name__ == "__main__":
    main()
