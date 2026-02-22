# Flexible Dockerfile to build/run OpenClaw from a repository URL
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG REPO_URL=https://github.com/Owen-Liuyuxuan/openclaw.git
ARG REPO_REF=main
ENV OPENCLAW_HOME=/opt/openclaw

RUN set -eux; \
      # try update with a couple of retries (network/DNS can be flaky in some envs)
      for i in 1 2 3; do apt-get update && break || sleep 2; done; \
      apt-get install -y --no-install-recommends --fix-missing \
         git curl ca-certificates python3 python3-pip nodejs npm build-essential || true; \
      rm -rf /var/lib/apt/lists/*

RUN set -eux; \
      mkdir -p ${OPENCLAW_HOME}; \
      if echo "${REPO_URL}" | grep -q "github.com"; then \
         repo_path="$(echo ${REPO_URL} | sed -E 's#https://github.com/##; s#(.git)$##')"; \
         if curl -fSL -o /tmp/openclaw.tar.gz "https://github.com/${repo_path}/archive/refs/heads/${REPO_REF}.tar.gz" || curl -fSL -o /tmp/openclaw.tar.gz "https://github.com/${repo_path}/archive/${REPO_REF}.tar.gz"; then \
            extracted_dir=$(tar -tzf /tmp/openclaw.tar.gz | head -1 | cut -f1 -d"/"); \
            tar -xzf /tmp/openclaw.tar.gz -C /tmp; \
            mv /tmp/${extracted_dir}/* ${OPENCLAW_HOME}/; \
            rm -rf /tmp/openclaw.tar.gz /tmp/${extracted_dir}; \
         else \
            echo "Warning: failed to fetch ${REPO_URL}@${REPO_REF} from GitHub"; \
         fi; \
      else \
         git clone --depth 1 --branch ${REPO_REF} ${REPO_URL} ${OPENCLAW_HOME} || true; \
      fi; \
      if [ -z "$(ls -A ${OPENCLAW_HOME} 2>/dev/null)" ]; then \
         mkdir -p ${OPENCLAW_HOME}; \
         printf "print('OpenClaw placeholder app - repository fetch failed during build')\n" > ${OPENCLAW_HOME}/app.py; \
         printf "#!/bin/bash\npython3 app.py\n" > ${OPENCLAW_HOME}/start.sh; \
         chmod +x ${OPENCLAW_HOME}/start.sh; \
      fi
WORKDIR ${OPENCLAW_HOME}

# Install Python deps if present
RUN if [ -f requirements.txt ]; then pip3 install --no-cache-dir -r requirements.txt; fi

# Install Node deps if present
RUN if [ -f package.json ]; then npm install --no-audit --no-fund; fi

EXPOSE 18789

# Default entry: try common start scripts (start.sh, npm start, python app)
CMD ["bash","-lc","if [ -f start.sh ]; then exec bash ./start.sh; elif [ -f package.json ] && command -v npm >/dev/null 2>&1; then npm run start || npm start; elif [ -f app.py ]; then exec python3 app.py; else echo 'No entrypoint found — override CMD or provide repo with run script'; exec sleep infinity; fi"]
