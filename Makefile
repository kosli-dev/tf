.PHONY: pip test

pip: .venv
	.venv/bin/pip install -r requirements.txt

test: .venv
	.venv/bin/python -m pytest tests/ -v

.venv:
	python3 -m venv .venv
