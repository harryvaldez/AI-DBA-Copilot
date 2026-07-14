#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "==> Building all images"
docker compose build --parallel

echo "==> Starting all services"
docker compose up -d --wait --wait-timeout 180

FAILED=0
declare -A PORTS=(
  [copilot-ui]=3000
  [detection-engine]=8001
  [recommendation-engine]=8002
  [jira-integration]=8003
  [mcp-layer]=8004
  [memory-service]=8005
  [predictive-analytics]=8006
)

echo "==> Waiting for health endpoints"
for svc in copilot-ui detection-engine recommendation-engine jira-integration mcp-layer memory-service predictive-analytics; do
  port="${PORTS[$svc]}"
  echo "Waiting for $svc on port $port..."
  ok=0
  for _ in $(seq 1 30); do
    if curl -sf "http://localhost:${port}/health" > /dev/null; then
      echo "  ✓ Port $port healthy ($svc)"
      ok=1
      break
    fi
    sleep 2
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "  ✗ Port $port failed ($svc)"
    docker compose logs --tail=50 "$svc" || true
    FAILED=1
  fi
done

echo "==> Stopping stack"
docker compose down -v

if [[ "$FAILED" -ne 0 ]]; then
  echo "One or more health checks failed"
  exit 1
fi

echo "All services healthy"
