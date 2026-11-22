"""Run one public CourseLab process and two loopback services in the pilot."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REFLECTIONS_PORT = "8002"
SDL_PORT = "8100"
SOCRATIC_PORT = "8003"


def main():
    env = {
        **os.environ,
        "REFLECTIONS_URL": f"http://127.0.0.1:{REFLECTIONS_PORT}",
        "SELF_DIRECTED_LEARNING_URL": f"http://127.0.0.1:{SDL_PORT}",
        "SOCRATIC_URL": f"http://127.0.0.1:{SOCRATIC_PORT}",
        "ADAPTIVE_PLATFORM_ONLY": "true",
    }
    socratic_env = {**env, "SOCRATIC_SERVICE_MODE": "true"}
    services = [
        (sys.executable, ROOT, "platform_app.combined:app", "0.0.0.0", env.get("PORT") or "8000"),
        (sys.executable, ROOT, "platform_app.socratic_service:app", "127.0.0.1", SOCRATIC_PORT, socratic_env),
        ("/opt/reflections/bin/python", ROOT / "reflections-app/backend", "app.main:app", "127.0.0.1", REFLECTIONS_PORT),
        ("/opt/sdl/bin/python", ROOT / "self-directed-learning/backend", "app.main:app", "127.0.0.1", SDL_PORT),
    ]
    stopping = False

    def stop(_signal, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    children = []
    try:
        for service in services:
            python, cwd, app, host, port, *service_env = service
            process = subprocess.Popen(
                [python, "-m", "uvicorn", app, "--host", host, "--port", port, "--workers", "1"],
                cwd=cwd, env=service_env[0] if service_env else env,
            )
            children.append((cwd.name, process))
        while not stopping:
            for name, process in children:
                if process.poll() is not None:
                    print(f"{name} exited with status {process.returncode}", file=sys.stderr)
                    return 1
            time.sleep(0.2)
        return 0
    finally:
        for _, process in children:
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 8
        for _, process in children:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    sys.exit(main())
