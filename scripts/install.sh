#!/usr/bin/env bash
# Dependency install with the Scalekit <-> Actian protobuf fix.
#
# scalekit-sdk-python pins protobuf<7.0.0, which silently downgrades the protobuf
# version actian-vectorai-client needs. Fix: install Scalekit with --no-deps, then
# reassert protobuf>=6.31.1 and grpcio-status>=1.67.0 (already in requirements.txt).
set -euo pipefail

echo "==> Installing base requirements"
pip install -r requirements.txt

echo "==> Installing Scalekit SDK WITHOUT its deps (avoids the protobuf<7 downgrade)"
pip install scalekit-sdk-python --no-deps

echo "==> Restoring Scalekit's runtime deps EXCEPT the ones that conflict with Actian"
pip install pyjwt cryptography cffi deprecation requests protoc-gen-openapiv2

echo "==> Reasserting protobuf / grpcio-status versions the Actian client needs"
echo "    (overrides Scalekit's protobuf<7 and grpcio-status<1.67 caps -- intentional)"
pip install "protobuf>=6.31.1,<7" "grpcio-status>=1.67.0"

if [ -n "${ACTIAN_WHEEL:-}" ]; then
  echo "==> Installing Actian VectorAI client from ${ACTIAN_WHEEL}"
  pip install "${ACTIAN_WHEEL}"
else
  echo "==> ACTIAN_WHEEL not set. Set ACTIAN_WHEEL=/path/to/actian_vectorai-*.whl"
  echo "    (or 'pip install actian-vectorai-client') to enable vector memory."
fi

echo "==> Verifying dependency tree"
pip check || echo "(pip check reported issues — review the output above)"

echo "==> Smoke importing critical packages"
python - <<'PY'
import importlib
for mod in ("fastapi", "psycopg", "openai", "scalekit"):
    try:
        importlib.import_module(mod)
        print(f"  ok: {mod}")
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL: {mod} -> {e}")
for mod in ("actian_vectorai",):
    try:
        importlib.import_module(mod)
        print(f"  ok: {mod}")
    except Exception as e:  # noqa: BLE001
        print(f"  skip: {mod} (not installed) -> {e}")
PY

echo "==> Done."
