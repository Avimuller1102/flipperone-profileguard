.PHONY: install check lint test demo upstream-sh clean

install:
	python -m pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .
	mypy

test:
	python -m pytest

check: lint test

# Offline demo: the bundled upstream snapshot, then the synthetic regression being caught.
demo:
	profileguard doctor
	profileguard test --all-awks --html profileguard-report.html || true
	profileguard compare --baseline snapshot --candidate synthetic-defect --all-awks || true

# Run the proposed upstream shell test against a flipperos-btrfs-tools checkout: make upstream-sh UPSTREAM=../flipperos-btrfs-tools
upstream-sh:
	@test -n "$(UPSTREAM)" || { echo "set UPSTREAM=path/to/flipperos-btrfs-tools"; exit 2; }
	cp upstream-proposal/tests/accountdb-merge.sh "$(UPSTREAM)/tests/accountdb-merge.sh"
	sh "$(UPSTREAM)/tests/accountdb-merge.sh"

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache .ruff_cache .hypothesis profileguard-report.html
