#!/usr/bin/env python3
"""Single entry point: runs the Telegram bot and the web admin panel together.

All administration tasks live in the Flask panel; the bot itself only serves
end users. Both are launched as separate processes on purpose: each one needs
its own asyncio event loop, and the SQLAlchemy async engine binds its pooled
connections to the loop that created them. Sharing a single process would mix
loops and break the engine. SQLite runs in WAL mode, so concurrent access from
both processes is safe.
"""

import os
import signal
import subprocess
import sys
import threading

from bot.config import settings

PROCESSES = [
    ("bot", [sys.executable, "-m", "bot.main"]),
    ("web", [sys.executable, "-m", "web.app"]),
]

COLORS = {"bot": "\033[36m", "web": "\033[35m"}
RESET = "\033[0m"

_running: list = []
_shutting_down = threading.Event()


def _stream_output(name: str, proc: subprocess.Popen) -> None:
    """Forward a child's output to our stdout, prefixed with its name."""
    color = COLORS.get(name, "")
    for line in iter(proc.stdout.readline, ""):
        sys.stdout.write(f"{color}[{name}]{RESET} {line}")
        sys.stdout.flush()


def _shutdown(*_args) -> None:
    """Terminate every child process, escalating to kill if needed."""
    if _shutting_down.is_set():
        return
    _shutting_down.set()

    print("\n⏹  Deteniendo servicios...")
    for name, proc in _running:
        if proc.poll() is None:
            proc.terminate()

    for name, proc in _running:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print(f"⚠️  '{name}' no respondió al cierre, forzando kill.")
            proc.kill()


def main() -> int:
    if not settings.BOT_TOKEN:
        print("\n" + "=" * 60)
        print("⚠️  FALTA BOT_TOKEN!")
        print("Copiá .env.example a .env y completá tu BOT_TOKEN.")
        print("Conseguí un token con @BotFather en Telegram.")
        print("=" * 60 + "\n")
        return 1

    # Unbuffered children so their logs stream live instead of in chunks.
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    for name, cmd in PROCESSES:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        _running.append((name, proc))
        threading.Thread(target=_stream_output, args=(name, proc), daemon=True).start()

    print("\n" + "=" * 60)
    print("🤖 Bot de Telegram: iniciado")
    print(f"🖥  Panel de administración: http://{settings.WEB_ADMIN_HOST}:{settings.WEB_ADMIN_PORT}")
    print("   (Ctrl+C para detener ambos)")
    print("=" * 60 + "\n")

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # If either service dies, bring the whole stack down rather than running degraded.
    exit_code = 0
    try:
        while not _shutting_down.is_set():
            for name, proc in _running:
                code = proc.poll()
                if code is not None:
                    print(f"\n❌ El proceso '{name}' terminó con código {code}.")
                    exit_code = code or 1
                    _shutdown()
                    break
            else:
                threading.Event().wait(0.5)
                continue
            break
    finally:
        _shutdown()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
