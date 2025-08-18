# Contributing to wallapop-auto-adjust

We’re happy you’re here. Whether it’s your first PR or your hundredth, you’re welcome. This guide keeps things simple so you can focus on making great improvements.

## Code of Conduct
Be kind, be curious, and help each other grow. By participating, you agree to uphold a welcoming, harassment‑free environment. If something feels off, please open an issue or contact the maintainer.

## Ways to contribute
No contribution is too small. You can:
- Report bugs and propose improvements via [Issues](https://github.com/Alexander-Serov/wallapop-auto-adjust/issues)
- Polish documentation (README, examples, comments)
- Implement small fixes and quality‑of‑life improvements
- Pitch and prototype bigger features
- Add tests for existing or new behavior

## Getting started (dev setup)
You’ll need Python 3.10+ and Poetry.

1) Clone and install:
```bash
poetry install
```
2) Run tests:
```bash
poetry run pytest -q
```
3) Try the CLI locally:
```bash
poetry run wallapop-auto-adjust
```
Notes:
- First run may open a browser to log in; the session is cached for ~24h.
- Local files `products_config.json`, `wallapop_session.json` are for your machine only (ignored by git).
- If you get stuck, open a draft PR or issue—we’re happy to help.

## Development workflow
- Fork the repo and create a feature branch from `main`.
- Keep PRs focused and small; add tests when changing behavior.
- Update docs when you change user‑facing behavior.
- Prefer incremental progress over perfection—small steps are great.

### Formatting & style
- Use Black for formatting:
```bash
poetry run black .
```
- Follow idiomatic Python; prefer clear names and small functions.
- Type hints are welcome but not required.

### Testing
- Tests live under `tests/` and are collected by pytest.
- Add at least a happy‑path test (expected behavior) and one edge case for new logic.
- Run tests locally before opening a PR:
```bash
poetry run pytest -q
```

## Pull Requests
Before submitting a PR, please check:
- [ ] Tests pass locally (`pytest -q`)
- [ ] New/changed behavior is covered by tests
- [ ] Docs updated (README/CHANGELOG) when relevant
- [ ] No secrets or personal data in code, config, or logs

Commit style: clear, imperative messages. Conventional Commits are appreciated but not required. Screenshots are encouraged when UI/UX changes.

## Issue reports
When filing an issue, please include:
- What you expected vs. what happened
- Steps to reproduce (ideally minimal)
- Environment (OS, Python version)
- Relevant logs or stack traces (scrub personal data)
If you’re unsure how to describe it, just tell us the story—what you tried, what you saw, and what you expected.

## Releases (maintainers)
- Update `CHANGELOG.md`
- Bump version via Poetry, e.g.:
```bash
poetry version patch   # or minor / major
```
- Commit and tag with `vX.Y.Z`, then push tags. GitHub Actions will build and publish to PyPI.
- Ensure repo secret `PYPI_TOKEN` is set (used by the release workflow).

Thank you for contributing—your ideas make this project better. We can’t wait to see what you build.
