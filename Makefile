.PHONY: install build dev test run
install:
	pip install -r requirements.txt
	cd web && npm ci
build:
	cd web && npm run build
dev:   ## API on :8640 + Vite dev server on :5173 with hot reload
	python run.py --no-browser & cd web && npm run dev
test:
	python -m pytest -q
run:
	python run.py
