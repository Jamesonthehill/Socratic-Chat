"""Public entry point for the combined Docker pilot."""
from urllib.error import URLError
from urllib.request import urlopen

from fastapi.responses import JSONResponse

from platform_app.main import app


@app.get("/health/combined", include_in_schema=False)
def combined_health():
    statuses = {"platform": True}
    for service, url in (
        ("socratic", "http://127.0.0.1:8003/health"),
        ("reflections", "http://127.0.0.1:8002/health"),
        ("sdl", "http://127.0.0.1:8100/api/health"),
    ):
        try:
            with urlopen(url, timeout=1) as response:
                statuses[service] = response.status == 200
        except (URLError, OSError):
            statuses[service] = False
    healthy = all(statuses.values())
    return JSONResponse(status_code=200 if healthy else 503, content={"services": statuses})


# Place the health route before the platform's catch-all static mount.
app.router.routes.insert(-1, app.router.routes.pop())
