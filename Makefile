TOX=tox

.PHONY: lint
lint:
	$(TOX) -c tox.ini -e lint

.PHONY: coverage
coverage:
	$(TOX) -c tox.ini -e coverage

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
	$(TOX) -c tox.ini -e test

.PHONY: upload-release
upload-release:
	python setup.py register sdist upload

.PHONY: yamllint
yamllint:
	yamllint --strict .github/workflows/main.yml
