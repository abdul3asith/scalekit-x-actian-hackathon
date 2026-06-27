.PHONY: install db-up db-down run seed test vapi fmt

# Install deps with the Scalekit<->Actian protobuf fix (set ACTIAN_WHEEL to enable memory).
install:
	bash scripts/install.sh

# Start Postgres (schema auto-applies on first boot).
db-up:
	docker compose up -d postgres

db-down:
	docker compose down

# Run the backend (VAPI custom-LLM endpoint + web onboarding).
run:
	uvicorn app.main:app --reload --port 8000

# Seed reproducible demo staff + shifts.
seed:
	python scripts/seed_demo.py

# Run the test suite (DB integration tests skip if Postgres is down).
test:
	pytest -q

# Create the VAPI assistant pointing at PUBLIC_BASE_URL.
vapi:
	python scripts/setup_vapi_assistant.py
