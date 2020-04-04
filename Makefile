.PHONY: clean install install-all version

help:
	@echo "clean - remove artifacts"
	@echo "test - run unit test and test buildkite plugin"

clean: clean-build

clean-build:
	rm -rf build/
	rm -rf dist/
	find . -type d -name __pycache__ -exec rm -r {} \+
	rm -rf .eggs
	rm -rf .pytest_cache
	rm -rf *.egg-info

install: clean-build
	python setup.py install

install-all:
	pip install -e .[all]

lint: lint-plugin lint-python

lint-plugin:
	docker-compose run --rm linter

lint-python:
	pytest --flake8 buildpipe tests

test: test-unit test-plugin

test-unit:
	python setup.py test

test-plugin:
	docker-compose up --build tests

version:
	python setup.py --version
