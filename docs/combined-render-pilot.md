# CourseLab combined Render pilot

The combined image starts CourseLab on Render's `PORT` and runs Reflections and SDL on loopback ports 8002 and 8100. Each Python app has its own dependency environment. The public `/health/combined` endpoint reports ready once all three apps respond.

## Local Starter-sized run

Run these commands from the repository root. Use a disposable database, as the apps initialize their schemas on startup.

```sh
docker build -f Dockerfile.combined -t courselab-combined-pilot .
docker network create courselab-pilot-local
docker run -d --name courselab-pilot-db --network courselab-pilot-local \
  -e POSTGRES_PASSWORD=pilot-test-only pgvector/pgvector:pg16
docker exec courselab-pilot-db pg_isready -U postgres
docker run -d --name courselab-pilot-app --network courselab-pilot-local \
  --memory=512m --memory-swap=512m --cpus=0.5 -p 127.0.0.1:18000:8000 \
  -e DATABASE_URL=postgresql://postgres:pilot-test-only@courselab-pilot-db:5432/postgres \
  -e AUTH_SESSION_SECRET=local-pilot-session-secret \
  -e PLATFORM_SERVICE_TOKEN=local-pilot-service-token \
  courselab-combined-pilot
curl -fsS http://127.0.0.1:18000/health/combined
docker stats --no-stream courselab-pilot-app
docker exec courselab-pilot-app cat /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.events
```

Wait for PostgreSQL readiness before starting the application. Give the application time to initialize its schemas before checking health. To clean up, remove the two pilot containers and their network.

## Render trial

Create a separate Blueprint using `render.combined.yaml` from `main`. It creates one paid Starter web service. Use the pilot service's public URL for `FRONTEND_URL` and `LTI_PUBLIC_BASE_URL` and supply a test database and the provider credentials in Render. Configure a separate Canvas test launch for this URL. The Blueprint uses the repository's existing model defaults.

Measure peak memory and request latency during PDF ingestion, simultaneous Socratic/Reflection/SDL turns, and an AIDucate report. Use synthetic records or an approved test course. Check logs for worker exits and compare latency against the current deployment before moving student traffic.

## First local run

On Docker Desktop (ARM64) at 512 MiB and 0.5 CPU, all three services became healthy. A disposable PostgreSQL container ran outside the application's memory budget, matching the intended external database setup. The application used about 388 MiB just after startup. A run of 30 local page and health requests at concurrency five measured 40 ms p95, rising to 92 ms while a 75-row synthetic AIDucate HTML report started. The report completed in 2.2 seconds and the container touched the 512 MiB memory limit without an OOM kill. A synthetic text PDF parsed successfully through SDL's lightweight internal endpoint in 30 ms.

These timings exclude real model calls, external database latency, Canvas launches, and Docling/OCR processing. Check those workloads on the pilot before switching the class deployment.
