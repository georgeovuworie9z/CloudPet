# CloudPet

CloudPet is a production-style pet management REST API built as a hands-on AWS cloud engineering portfolio project.

## Technology

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Docker
- AWS

## Architecture

The application is designed to run as a stateless FastAPI service behind an AWS Application Load Balancer, with PostgreSQL on Amazon RDS and pet images stored in Amazon S3.

## Running with Docker

This runs the API and PostgreSQL locally via Docker Compose. It's for local development only — see `docker-compose.yml` for details; production AWS deployment is a separate, later milestone.

```bash
docker compose up -d --build
```

Check that both containers are up and the API is healthy:

```bash
docker compose ps
curl -i http://localhost:8000/health
```

The API is then available at `http://localhost:8000` (interactive docs at `/docs`).

Database migrations are **not** run automatically when the API container starts — this is intentional, so multiple instances starting concurrently never race on a migration. Apply them explicitly:

```bash
docker compose exec api alembic upgrade head
```

To stop the stack:

```bash
docker compose down
```

Add `-v` to also remove the PostgreSQL data volume.

## Project Status

🚧 Initial development

## Development Model

Backend application development is assisted by Claude Code.

AWS infrastructure is designed and implemented manually by the project owner.

ChatGPT is used as the project's architecture and technical review assistant.