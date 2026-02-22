# OpenClaw Docker helper

This folder contains a flexible Dockerfile that clones an OpenClaw repository and attempts to install/run it. Adjust `REPO_URL` and `REPO_REF` build args if you want a specific repository or branch.

Build the image (from workspace root):

```powershell
docker build -t openclaw-docker -f docker/openclaw/Dockerfile \
  --build-arg REPO_URL=https://github.com/Owen-Liuyuxuan/openclaw.git \
  --build-arg REPO_REF=main .
```

Run the container mapping the Gateway port:

```powershell
docker run -d -p 18789:18789 --name openclaw openclaw-docker
```

Notes:
- The Dockerfile installs both Python and Node tooling and will run common entrypoints in this order: `start.sh`, `npm run start` / `npm start`, `python3 app.py`.
- If the upstream repo uses a different command, override the image `CMD` or provide a `start.sh` in the repo.
- If an official `openclaw/openclaw` image exists, prefer pulling it instead: `docker pull openclaw/openclaw:latest`.

If you want, I can:

- Produce a Dockerfile tailored to the OpenClaw repo's actual runtime (I can inspect the repo if you give the URL), or
- Create a small `docker-compose.yml` fragment for local development.
