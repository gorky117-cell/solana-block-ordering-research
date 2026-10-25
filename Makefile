.PHONY: test dry-run benchmark report docker-build docker-run clean

test:
	python -m unittest discover tests

dry-run:
	python -m src.cli --benchmark-all --generate-report

report:
	python -m src.cli --generate-report

docker-build:
	docker compose build

docker-run:
	docker compose up --build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
