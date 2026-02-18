# Security Policy

## Supported Versions

Only the latest version on the `main` branch receives security patches.

| Version / Branch | Supported          |
| ---------------- | ------------------ |
| `main` (latest)  | :white_check_mark: |
| Older tags/SHA   | :x:                |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Use GitHub's built-in **private vulnerability reporting** instead:

1. Go to the [Security tab](https://github.com/dongju93/cooking-recipe-api/security) of this repository.
2. Click **"Report a vulnerability"**.
3. Fill in the form with as much detail as possible (see below).

This keeps the report confidential until a fix is ready and a coordinated disclosure can be made.

## What to Include in Your Report

To help reproduce and triage the issue quickly, please provide:

- **Description** — a clear summary of the vulnerability and its potential impact.
- **Affected component** — e.g., authentication endpoint, serializer, Docker configuration.
- **Steps to reproduce** — a minimal, self-contained example or curl/HTTP request sequence.
- **Expected vs. actual behaviour** — what should happen vs. what actually happens.
- **Environment** — Python version, Django version, DRF version, OS, Docker version (if relevant).
- **Suggested fix** (optional) — any patch, workaround, or reference you think is relevant.

## Response Timeline

| Stage                          | Target timeframe                                 |
| ------------------------------ | ------------------------------------------------ |
| Initial acknowledgement        | Within **3 business days**                       |
| Triage and severity assessment | Within **7 days**                                |
| Patch or mitigation available  | Within **30 days** (critical issues prioritised) |
| Public disclosure              | After patch is released and reporter is notified |

These are best-effort targets for a personal project; complex issues may take longer.

## Disclosure Policy

- Reporters will be credited in the release notes / commit message unless they prefer to remain anonymous.
- We follow a **coordinated disclosure** model: please allow time for a fix before public disclosure.
- If a fix cannot be delivered within 90 days, we will notify you and agree on a disclosure date together.

## Scope

### In scope

| Area                                 | Examples                                                                                  |
| ------------------------------------ | ----------------------------------------------------------------------------------------- |
| **Authentication & authorisation**   | Token exposure, missing `IsAuthenticated` guard, privilege escalation                     |
| **Serializer / input validation**    | Mass-assignment, missing field validation, insecure deserialization                       |
| **SQL / ORM injection**              | Raw query injection via unsanitised user input                                            |
| **Sensitive data exposure**          | Credentials logged, secrets in environment variables committed to repo                    |
| **Docker / container configuration** | Running as root unnecessarily, exposed ports, world-readable secrets                      |
| **Dependency vulnerabilities**       | Known CVEs in `Django`, `djangorestframework`, `psycopg`, or other direct dependencies    |
| **API security**                     | IDOR/BOLA, broken object-level authorisation, unauthenticated access to private resources |

### Out of scope

- Vulnerabilities in indirect / transitive dependencies that do not affect this project's attack surface.
- Issues requiring physical access to the host machine.
- Spam, social engineering, or denial-of-service attacks against the running service.
- Vulnerabilities in third-party services (GitHub Actions runners, Docker Hub, etc.).
- Missing security headers on a development-only server (`DEBUG=True`).

## Security Best Practices in This Project

The following controls are already in place; reports about these are unlikely to be accepted unless a bypass is demonstrated:

- Custom `User` model with email-based authentication (no default `admin`/`admin` credentials).
- `TokenAuthentication` + `IsAuthenticated` enforced project-wide via DRF settings.
- No credentials hardcoded — all secrets loaded from environment variables (`.env.local`, Docker secrets).
- `psycopg` (psycopg3) parameterised queries used throughout — raw SQL avoided.
- Multi-stage Docker build; application does not run as `root` inside the container.
- CI pipeline runs `ruff` (lint), `pyrefly` (type check), and the full test suite on every push.

## Preferred Languages

Reports may be written in **English** or **Korean (한국어)**.
