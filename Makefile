VENV = .venv
PYTHON = $(VENV)/bin/python
# Via the interpreter, so a venv whose console scripts are missing or
# non-executable still works.
PIP = $(PYTHON) -m pip

all: venv

$(VENV)/bin/activate: pyproject.toml
	python3 -m venv $(VENV)
	$(PIP) install -U pip
	# Editable, so `make test` tests the tree rather than a snapshot of it
	$(PIP) install -e . flake8

venv: $(VENV)/bin/activate

run: venv
	$(VENV)/bin/tabview $(ARGS)

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf $(VENV) build dist *.egg-info

# Run the test suite. The integration tests use curses, so this needs a
# terminal (CI runs it under script(1) for a pty).
# Usage: make test [TEST_ARGS="-k search -v"]
test: venv
	$(PYTHON) -W error -m unittest discover $(TEST_ARGS)

lint: venv
	$(VENV)/bin/flake8 --extend-ignore E501 tabview test

# Print the version recorded in tabview/__init__.py
version:
	@grep -Po '^__version__ = "\K[^"]+' tabview/__init__.py

# Bump __version__, turn the CHANGELOG's *Unreleased* heading into the
# version and date, commit, and create an annotated tag. $EDITOR prefilled
# with version and commits since the last tag.
# Usage: make release VERSION=1.5.0
release:
	@test -n "$(VERSION)" || { echo "Usage: make release VERSION=x.y.z"; exit 1; }
	@echo "$(VERSION)" | grep -Pq '^\d+\.\d+\.\d+$$' || \
		{ echo "VERSION must be x.y.z"; exit 1; }
	@test -z "$$(git status --porcelain -uno)" || \
		{ echo "Tracked files have uncommitted changes; commit or stash first"; exit 1; }
	@git rev-parse -q --verify refs/tags/$(VERSION) >/dev/null && \
		{ echo "Tag $(VERSION) already exists"; exit 1; } || true
	@grep -q '^\*Unreleased\*$$' CHANGELOG.rst || \
		{ echo "CHANGELOG.rst has no *Unreleased* section to release"; exit 1; }
	sed -i 's/^__version__ = ".*"$$/__version__ = "$(VERSION)"/' tabview/__init__.py
	sed -i "s|^\*Unreleased\*$$|*Version $(VERSION) $$(date '+%Y/%m/%d')*|" \
		CHANGELOG.rst
	@test "$$($(MAKE) -s version)" = "$(VERSION)" || \
		{ echo "Failed to set version"; exit 1; }
	git commit -m "Bump version to $(VERSION)" tabview/__init__.py CHANGELOG.rst
	# Open the tag message prefilled with the version as the subject and one
	# bullet per commit since the last tag.
	@notes=$$(mktemp); \
	prev=$$(git describe --tags --abbrev=0 2>/dev/null); \
	{ echo "$(VERSION)"; echo; \
	  git log --no-merges --invert-grep \
		--grep='^Bump version to ' --format='* %s' \
		$${prev:+$$prev..}HEAD; } > $$notes; \
	git tag -a -e -F $$notes $(VERSION); status=$$?; \
	rm -f $$notes; \
	test $$status -eq 0 || exit $$status; \
	test -n "$$(git for-each-ref --format='%(contents:body)' \
		refs/tags/$(VERSION))" || { \
		git tag -d $(VERSION) >/dev/null; \
		echo "Tag message body is empty, so the release notes would be too."; \
		echo "Tag not created. The version bump commit is still there;"; \
		echo "undo it with: git reset --hard HEAD^"; \
		exit 1; }
	@echo
	@echo "Tagged $(VERSION). Push with:"
	@echo "    git push origin $$(git rev-parse --abbrev-ref HEAD) --follow-tags"

.PHONY: all venv run clean test lint version release
