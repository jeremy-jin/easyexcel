SHELL = /bin/bash

HTMLCOV_DIR ?= htmlcov

# test
coverage-html: test
	 coverage html -d $(HTMLCOV_DIR) --fail-under 100

coverage-report: test
	coverage report -m

lint:
	flake8 src tests

test:
	coverage run --concurrency=eventlet --source=easyexcel -m pytest test $(ARGS)

black:
	black src tests

coverage: lint black coverage-html coverage-report test

