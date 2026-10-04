#!/usr/bin/env bash
# Project-local Linux service; run explicitly after a workspace restart.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
workspace_root="$(cd -- "$project_root/../.." && pwd)"
runtime_root="${PQA_RUNTIME_ROOT:-$workspace_root/.runtime}"
port="${PQA_OLLAMA_PORT:-11435}"
version="${PQA_OLLAMA_VERSION:-0.30.10}"
log_dir="$project_root/.cache/ollama-linux"
if [[ "$port" != 11435 ]]; then log_dir="$log_dir-$port"; fi
mkdir -p "$log_dir" "$runtime_root/models"
export OLLAMA_HOST="127.0.0.1:$port"
export OLLAMA_MODELS="$runtime_root/models"
export OLLAMA_CONTEXT_LENGTH=8192
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
export OLLAMA_KEEP_ALIVE=10m
export OLLAMA_NO_CLOUD=1
export OLLAMA_NOPRUNE=1
if curl --fail --silent --max-time 2 "http://$OLLAMA_HOST/api/version"; then
    printf '\nOllama already responds; its settings were not changed.\n'
    exit 0
fi
ollama_bin="$runtime_root/ollama-$version/bin/ollama"
test -x "$ollama_bin"
nohup "$ollama_bin" serve >"$log_dir/stdout.log" 2>"$log_dir/stderr.log" < /dev/null &
server_pid=$!
printf '%s\n' "$server_pid" > "$log_dir/server.pid"
for ((attempt=0; attempt<90; attempt++)); do
    if curl --fail --silent --max-time 2 "http://$OLLAMA_HOST/api/version"; then
        printf '\nOllama ready, PID %s; logs: %s\n' "$server_pid" "$log_dir"
        exit 0
    fi
    kill -0 "$server_pid" || { cat "$log_dir/stderr.log"; exit 1; }
    sleep 2
done
printf 'Ollama did not become ready; inspect %s\n' "$log_dir" >&2
exit 1
