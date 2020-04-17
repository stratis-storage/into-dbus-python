.PHONY: lint
lint:
	./check.py src/into_dbus_python
	./check.py tests

.PHONY: coverage
coverage:
	python3 -m coverage --version
	python3 -m coverage run --timid --branch -m unittest discover tests
	python3 -m coverage report -m --fail-under=100 --show-missing --include="./src/*"
	python3 -m coverage html --include="./src/*"

.PHONY: fmt
fmt:
	isort --recursive check.py setup.py src tests
	black .

.PHONY: fmt-travis
fmt-travis:
	isort --recursive --diff --check-only check.py setup.py src tests
	black . --check

.PHONY: test
test:
	python3 -m unittest discover --verbose tests

.PHONY: upload-release
upload-release:
	python3 setup.py register sdist upload

.PHONY: yamllint
yamllint:
	yamllint --strict .travis.yml
