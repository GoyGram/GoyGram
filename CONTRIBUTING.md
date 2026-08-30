# Contributing to GoyGram

Thanks for your interest in contributing.

## Getting started

```bash
git clone https://github.com/GoyGram/GoyGram.git
cd GoyGram
uv venv .venv && source .venv/bin/activate
uv pip install -e .
```

## Building the Rust core

The crypto and TL codec live in `ext_rust/`. After changing Rust code, rebuild with:

```bash
maturin develop --release --manifest-path ext_rust/Cargo.toml
```

## What we look for

- MTProto transport correctness — the auth flow, message handling, and salt/DC recovery are the most sensitive parts.
- Bot API coverage — methods, types, and webhook handling.
- Performance improvements to the Rust core and the zero-copy event objects.

## Before you open a PR

- Run the benchmarks in `benchmarks/` when touching the Rust core, and include the before/after numbers in the PR description.
- Keep existing code comments unchanged unless the change requires it.
- Rust lives in `ext_rust/`, the Python layer in `goygram/`.

## License

By contributing you agree that your work is licensed under AGPL-3.0.
