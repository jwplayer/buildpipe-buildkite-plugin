.PHONY: clean install install-all version

help:
	@echo "clean - remove artifacts"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tests on every Python version with tox"

clean: clean-build

clean-build:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info

install: clean-build
	python setup.py install

install-all:
	pip install -e .[all]

lint:
	pytest --flake8 buildpipe tests

test:
	python setup.py test

test-all:
	tox

version:
	python setup.py --version
