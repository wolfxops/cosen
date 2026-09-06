# Contributing to Cosen

Thank you for helping make Cosen better. This guide covers the basics.

## License and CLA

Cosen is licensed under the Apache License 2.0. By submitting a pull request,
you agree to the terms in [CLA.md](CLA.md). We will not merge external PRs
without an explicit CLA sign-off.

## Development setup

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/ -q
```

## Project conventions

- **Python 3.10+** with type hints.
- **No vendor SDK imports** in the gateway path. The public contract is
  OpenAI-compatible `/v1/chat/completions`.
- **Security scanners are deterministic first**. No required LLM-as-judge.
- **Local-first**: SQLite, no ClickHouse, no mandatory cloud account.
- **Tests**: pytest. Add a test for any new scanner, budget rule, or gateway
  behavior.
- **Keep the public contract stable**: paths, headers, error types, and the
  SQLite schema should only change with an explicit migration or major bump.

## Attribution headers

Tag requests with `X-COS-Feature`, `X-COS-Project`, `X-COS-User`, and
`X-COS-Session`. `X-Cosen-*` aliases are also accepted.

## What we need

- Bug fixes and test coverage for the gateway, scanners, cost/budget logic, and
  web app.
- Price updates in `cosen/data/pricing.yaml` with a source comment.
- Provider health checks, streaming handling, and embeddings support.
- Documentation and example clients.

## What we do not need yet

- Visual agent builders, RAG engines, prompt CMS, eval platforms, or
  ClickHouse migrations until the core loop is used daily.

## Pull request process

1. Open an issue or discussion first for large changes.
2. Keep PRs small and focused.
3. Ensure `pytest` passes and the mock server still starts:
   ```bash
   cosen serve --mock
   curl -s http://127.0.0.1:8080/api/health
   ```
4. Reference the issue in the PR description.
5. Wait for maintainer review.
