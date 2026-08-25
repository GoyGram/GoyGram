# Contributing to GoyGram

## Before opening a change

Read the current implementation and trace the complete affected path. Do not treat README claims as proof of behavior. Changes to MTProto, TL schema loading, serialization, authentication, vaults, transports, or dispatch require focused regression tests and a safe live verification plan.

Never include API hashes, bot tokens, phone numbers, auth keys, session files, vaults, server salts, login codes, passwords, or raw Telegram packets in commits, issues, logs, or pull requests.

## Development checks

Use a Python 3.11+ virtual environment. Keep the private regression suite outside this public repository. Run the local checks from that private checkout together with:

```bash
python -m compileall -q goygram ext_rust
cargo test --manifest-path ext_rust/Cargo.toml

git diff --check
```

For native changes, rebuild the extension with maturin and run the focused private regression tests again. A successful local unit test does not replace a live MTProto check for transport changes. Do not commit the private suite, local harnesses, caches, or credentials.

## MTProto changes

Keep the official schema and layer negotiation version-aware. Preserve unknown constructors and updates without silently returning success. Required TL fields must fail loudly when missing or malformed. Separate read-only live checks from controlled writes; test writes only with data owned by the test account and clean them up.

## Pull requests

Describe the behavioral contract, affected transports, migration or rollback path, tests run, live checks run, and known limitations. Keep unrelated refactors out of a bug fix. Do not modify existing source comments unless the change explicitly requires it.

## Security reports

Do not open a public issue for a suspected credential leak, authentication bypass, session compromise, or remotely exploitable vulnerability. Follow `SECURITY.md` and redact all proof data.
