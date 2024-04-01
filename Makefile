.PHONY: docs
docs:
	sphinx-build docs docs/_build

.PHONY: clean
clean:
	@rm -rf dist

.PHONY: dist
dist:
	@hatch build && twine check --strict dist/*

.PHONY: release
release: clean dist
	$(eval RELEASE_VERSION=$(shell hatch version))
	@read -p "Release ${RELEASE_VERSION} (type 'yes' to confirm)? " confirm; \
	if [ "$$confirm" = "yes" ]; then  \
          hatch publish; \
          git tag v${RELEASE_VERSION}; \
          git push origin v${RELEASE_VERSION}; \
	fi
