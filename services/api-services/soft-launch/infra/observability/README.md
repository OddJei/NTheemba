Prometheus + Grafana local setup

This folder provides a minimal Docker Compose setup to run Prometheus and Grafana locally for testing the `msme-engine` `/metrics` endpoint.

Quick start

1. Ensure your local `msme-engine` is running and exposing metrics on `http://localhost:8500/metrics`.
2. From the repo root run:

```bash
cd infra/observability
docker-compose -f docker-compose.metrics.yml up -d
```

3. Grafana is available at `http://localhost:3000` (default admin/admin).
4. Prometheus is available at `http://localhost:9090`.

Example Prometheus scrape job

If you manage your own Prometheus config, add a scrape job like this to `prometheus.yml` so Prometheus scrapes the msme-engine `/metrics` endpoint:

```yaml
scrape_configs:
	- job_name: 'msme-engine'
		metrics_path: /metrics
		static_configs:
			- targets: ['<host-or-ip>:8500']
```

Notes

- The Prometheus config in this repo uses `host.docker.internal:8500` which works with Docker Desktop on Windows/macOS. If you run `msme-engine` inside Docker update `prometheus/prometheus.yml` to use Docker service names (for example `msme-engine:8500`).
- The Grafana provisioning will auto-load dashboards placed in `grafana/dashboards/` (one scaffolded dashboard exists: `msme_engine_dashboard.json`).
- To enable multiprocess metrics for local testing, set `PROMETHEUS_MULTIPROC_DIR` to a writable directory and ensure your app workers write to it.

Troubleshooting

- If Prometheus shows `no data` for the target, confirm the `msme-engine` `/metrics` endpoint is reachable from the Prometheus container (use `docker exec -it soft_launch_prometheus /bin/sh` and `wget -qO- http://host.docker.internal:8500/metrics`).
- If metrics are missing for histograms or counters, ensure your app registers metrics before serving requests and that worker processes share `PROMETHEUS_MULTIPROC_DIR` when using multiple workers.

