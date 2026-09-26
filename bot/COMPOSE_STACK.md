# Ntheemba + WhatsApp Gateway Compose Stack

This folder is the stack root.

```text
ntheemba-phase0/
  docker-compose.yml              # one stack for both apps
  Dockerfile                      # Ntheemba FastAPI image
  .dockerignore
  ntheemba/                       # Python FastAPI app/package
  migrations/                     # PostgreSQL migrations
  scripts/                        # migration and validation scripts
  nds-whatsapp-gateway-v1.0.0/    # Node WhatsApp gateway image
```

## Services

- `ntheemba`: FastAPI app on `http://localhost:8000`
- `gateway`: WhatsApp gateway on `http://localhost:8080`
- `waha`: private WhatsApp provider container
- `redis`: shared Redis used by Ntheemba runtime and gateway streams
- `postgres`: durable Ntheemba storage
- `ntheemba-migrate`: one-shot PostgreSQL migration job

## Commands

From this directory:

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

The default startup runs the Ntheemba core only. The WhatsApp provider image is large,
so it is behind the `whatsapp` profile.

Start the full WhatsApp stack. By default this uses WAHA's lighter `NOWEB`
image. Set `WAHA_IMAGE` and `WAHA_ENGINE` first if you specifically need
the Chromium/WEBJS image.

```powershell
docker compose --profile whatsapp pull waha
docker compose --profile whatsapp build
docker compose --profile whatsapp up -d
docker compose --profile whatsapp ps
```

Use the original Chrome/WEBJS provider:

```powershell
$env:WAHA_IMAGE="devlikeapro/waha:chrome-2026.7.2"
$env:WAHA_ENGINE="WEBJS"
docker compose --profile whatsapp pull waha
docker compose --profile whatsapp up -d
```

If WAHA pull keeps failing with `net/http: TLS handshake timeout`, reset any
Chrome override and retry the lighter image:

```powershell
Remove-Item Env:\WAHA_IMAGE -ErrorAction SilentlyContinue
Remove-Item Env:\WAHA_ENGINE -ErrorAction SilentlyContinue
docker compose --profile whatsapp pull waha
```

If it still times out, Docker is opening too many parallel layer downloads for
the connection. In Docker Desktop, open Settings -> Docker Engine and add:

```json
{
  "max-concurrent-downloads": 1
}
```

Apply & Restart Docker Desktop, then run:

```powershell
docker compose --profile whatsapp pull waha
docker compose --profile whatsapp up -d
```

Check logs:

```powershell
docker compose logs -f ntheemba
docker compose --profile whatsapp logs -f gateway
docker compose --profile whatsapp logs -f waha
```

Open:

- Ntheemba API docs: `http://localhost:8000/docs`
- Ntheemba health: `http://localhost:8000/health`
- Gateway health: `http://localhost:8080/health`

Stop:

```powershell
docker compose down
```

Remove containers and local volumes:

```powershell
docker compose down -v
```
