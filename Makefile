package=display_switch

.PHONY: clean build clean-build clean-pyc clean-test docs docs-serve format lint check lint-check install sync test coverage

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

build: clean
	uv build

clean-build: ## remove build artifacts
	rm -fr out/
	rm -fr build/
	rm -fr .build/
	rm -fr dist/
	rm -fr .eggs/
	rm -fr .tox .ruff_cache .mypy_cache
	rm -fr cov.xml
	rm -fr coverage.xml
	rm -fr dump.rdb
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr tests/.pytest_cache

docs: ## build the MkDocs documentation site
	uv run mkdocs build


docs-serve: ## preview documentation with live reload
	uv run mkdocs serve


format: ## apply safe Ruff fixes and format Python files
	uv run ruff check --fix .
	uv run ruff format .
	uv run black .
	uv run isort --profile black .


lint:
	uv run ruff check .
	uv run black --check .
	uv run isort --check-only --profile black .
	uv run pylint --exit-zero src
	uv run mypy --ignore-missing-imports src


check:
	uv run mypy src


lint-check: lint check

install: clean
	uv sync --no-dev

sync: ## install or update the project environment and dependencies
	uv sync

test: ## run tests quickly with the default Python
	uv run pytest ./tests


coverage: ## create an HTML coverage report
	uv run pytest ./tests
	@echo "Coverage HTML report is available at htmlcov/index.html"

