# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in ollama-log-proxy, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, report it privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability** (https://github.com/The-Bash/ollama-log-proxy/security/advisories/new). Include:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You should receive a response within 48 hours.

## Scope

Security concerns for this project include:

- Authentication bypass on dashboard/metrics endpoints
- Proxy request smuggling
- Log injection attacks
- Denial of service via oversized requests
- Information disclosure via error messages or logs
- SQL injection in SQLite/PostgreSQL backends
