.PHONY: clean test version

help:
	@echo "clean - remove artifacts"
	@echo "test - run unit test and test buildkite plugin"

clean: clean-build

clean-build:
	rm -rf build/
	rm -rf dist/
	find . -type d -name __pycache__ -exec rm -r {} \+
	rm -rf .eggs
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf *.egg-info
	rm -rf .buildpipe

lint: lint-plugin

lint-plugin:
	docker-compose run --rm buildkite_plugin_linter

test: test-unit test-plugin

test-unit:
	python setup.py test

test-plugin:
	docker-compose up --build buildkite_plugin_tester

version:
	python setup.py --version
