# Security Policy

## Supported versions

Security fixes are applied to the latest `main` branch and the latest published release. Users should upgrade before reporting a problem that is already fixed upstream.

## Reporting a vulnerability

Do not publish credentials, auth keys, vault contents, login codes, raw MTProto packets, or exploit details in a public issue. Report privately to the project maintainers through the private security contact configured for the repository, or through GitHub's private vulnerability reporting when enabled.

Include:

- affected commit or release;
- precise file and behavior;
- safe reproduction without real credentials;
- impact and required preconditions;
- proposed mitigation if known.

Allow maintainers reasonable time to investigate and release a fix. Do not test against accounts, chats, servers, or data that you do not own or have explicit permission to use.

## Secret exposure

If a token, API hash, auth key, vault, or login code was exposed, revoke or rotate it immediately before reporting. Never paste the secret into the report.
