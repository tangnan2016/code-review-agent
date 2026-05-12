.PHONY: install run test lint clean

install:
	pip install -r requirements.txt

run:
	python run.py $(ARGS)

test:
	python -m pytest test/ -v

lint:
	python -m flake8 src/ --max-line-length=120
	python -m mypy src/ --ignore-missing-imports

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache