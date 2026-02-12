# Container Health Monitor

This small Flask app exposes a few routes to monitor container health (CPU, memory and a health score). Below are all routes and example outputs in JSON format.

## Routes

- **GET /**
  - Description: Web UI landing page. Returns HTML (not JSON).

- **GET /logs**
  - Description: Web UI for viewing stored history in browser `localStorage`. Returns HTML (not JSON).

- **GET /api/analyze**
  - Description: Primary JSON API that analyzes current CPU and memory metrics, computes a health score and returns container info.
  - Example response (values are illustrative):

```json
{
  "machine_time": "2026-02-12 15:04:23",
  "health_score": 87,
  "cpu_metric": {
    "current": 3.45,
    "highest": 12.34,
    "lowest": 0.0,
    "average": 4.12
  },
  "memory_metric": {
    "total_mb": 1024.0,
    "used_mb": 256.0,
    "available_mb": 768.0,
    "current": 25.0,
    "highest": 37.5,
    "source_engine": "proc_meminfo"
  },
  "container_info": {
    "uptime_seconds": 12.34,
    "engine": "proc_meminfo",
    "cpu_cores": 2
  }
}
```

### Field descriptions

- `machine_time` — timestamp string when the analysis ran.
- `health_score` — integer 0–100 computed by `calculate_health_score()` using CPU%, memory% and uptime.
- `cpu_metric` — object with `current`, `highest`, `lowest`, `average` CPU percentages (rounded to 2 decimals).
- `memory_metric` — object with memory values in MB and percentages; `source_engine` indicates whether memory is read from cgroup v2 (`cgroup_v2`) or `/proc/meminfo` (`proc_meminfo`).
- `container_info.uptime_seconds` — seconds since the app started.
- `container_info.cpu_cores` — number of CPU cores detected by `os.cpu_count()`.

## Notes

- The API uses cgroup files when available (typical in containers). If those files are unavailable (e.g., not running on Linux or without cgroups), the implementation falls back to safer defaults.
- `/` and `/logs` return rendered HTML pages (see deploy_app/main.py), only `/api/analyze` returns JSON.

