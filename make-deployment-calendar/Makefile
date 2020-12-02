init: venv
	. venv/bin/activate; venv/bin/pip3 install -Ur requirements.txt

venv:
	python3 -m venv ./venv

test:
	pytest tests.py

.PHONY: init test
