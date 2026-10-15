# Agent Rules

Instructions for AI agents working on this codebase.

## Pull Requests

- **PR titles must always start with** `feat:` or `refactor:` (e.g. `feat: add X`, `refactor: simplify Y`).
- **PR descriptions must always be in-depth**: include a clear summary, detailed breakdown of changes by area, and rationale where relevant. Avoid one-line or minimal descriptions.

## Local Environment

- **Never install anything on the host machine.** Do not run `npm install`, `pip install`, `poetry install`, or any other package manager on the user's local system.
- All dependencies are installed inside Docker containers via the project's Dockerfile(s).

## Testing

- **Never install dependencies on the user's local machine.** CI runs backend tests with pip + pytest on the GitHub Actions runner (see `.github/workflows/deploy.yml`).
- For a local one-off test run, use a throwaway container instead of the host Python, e.g.:
  `docker run --rm -v "$PWD/backend":/app -w /app python:3.12-slim sh -c "pip install '.[dev]' && pytest"`
- Frontend type checks/tests also go in a container, e.g. `docker run --rm -v "$PWD/frontend":/app -w /app node:22-alpine sh -c "npm ci && npm run build"`.
