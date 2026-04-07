# Contributing to ollama-log-proxy

Thanks for your interest in contributing. Here's how to get started.

## Development Setup

```bash
git clone https://github.com/The-Bash/ollama-log-proxy.git
cd ollama-log-proxy
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Write tests for your changes
4. Ensure all tests pass and linting is clean
5. Commit with a clear message in imperative mood ("Add X", not "Added X")
6. Open a pull request against `main`

## Adding a New Backend

1. Create a new file in `src/ollama_log_proxy/backends/`
2. Implement the `LogBackend` protocol (see `backends/__init__.py`)
3. Register it in `create_backend()` in `backends/__init__.py`
4. Add the backend choice to CLI args in `cli.py`
5. Write tests in `tests/test_backends.py`
6. Update the README backend comparison table

## Reporting Issues

Use the GitHub issue templates for bug reports and feature requests. Include reproduction steps and your environment details.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
