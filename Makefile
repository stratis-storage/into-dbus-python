ifeq ($(origin MONKEYTYPE), undefined)
  PYTHON = python3
else
  PYTHON = MONKEYTYPE_TRACE_MODULES=into_dbus_python monkeytype run
endif

MONKEYTYPE_MODULES = into_dbus_python._signature

.PHONY: lint
lint:
	pylint setup.py
	pylint src/into_dbus_python
	pylint tests
	bandit setup.py
	# Ignore B101 errors. We do not distribute optimized code, i.e., .pyo
	# files in Fedora, so we do not need to have concerns that assertions
	# are removed by optimization.
	bandit --recursive ./src --skip B101
	bandit --recursive ./tests
	pyright

.PHONY: test
test:
	${PYTHON} -m unittest discover --verbose tests

.PHONY: coverage
coverage:
	coverage --version
	coverage run --timid --branch -m unittest discover tests
	coverage report -m --fail-under=100 --show-missing --include="./src/*"

.PHONY: fmt
fmt:
	isort setup.py src tests
	black .

.PHONY: fmt-travis
fmt-travis:
	isort --diff --check-only setup.py src tests
	black . --check

.PHONY: upload-release
upload-release:
	python setup.py register sdist upload

.PHONY: yamllint
yamllint:
	yamllint --strict .github/workflows/main.yml

.PHONY: package
package:
	(umask 0022; python -m build; python -m twine check --strict ./dist/*)

.PHONY: legacy-package
legacy-package:
	python3 setup.py build
	python3 setup.py install

.PHONY: apply
apply:
	@echo "Modules traced:"
	@monkeytype list-modules
	@echo
	@echo "Annotating:"
	@for module in ${MONKEYTYPE_MODULES}; do \
	  monkeytype --verbose apply  --sample-count --ignore-existing-annotations $${module} > /dev/null; \
	done
