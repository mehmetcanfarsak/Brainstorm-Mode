.PHONY: test coverage clean install-project install-global

test:
	python3 tests/run_tests.py

coverage:
	python3 -m coverage run --source=core,agents/claude-code/hooks_scripts,agents/opencode/hooks_scripts tests/run_tests.py
	python3 -m coverage report --show-missing

install-project:
	@test -n "$(PROJECT)" || (echo "Usage: make install-project PROJECT=/path/to/your/project" && exit 1)
	bash agents/claude-code/setup.sh --project "$(PROJECT)"

install-global:
	bash agents/claude-code/setup.sh --global

uninstall-project:
	@test -n "$(PROJECT)" || (echo "Usage: make uninstall-project PROJECT=/path/to/your/project" && exit 1)
	bash agents/claude-code/setup.sh --uninstall --project "$(PROJECT)"

uninstall-global:
	bash agents/claude-code/setup.sh --uninstall --global

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	rm -f .coverage .coverage.* htmlcov
