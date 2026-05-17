# SwimStats Chile

**SwimStats Chile** is a data platform for Chilean competitive swimming results, athletes and clubs.

The project transforms fragmented competition results, mostly published as PDFs or event-specific files, into structured, auditable and queryable data. It combines a backend ingestion pipeline, a PostgreSQL core model, a FastAPI layer and a React frontend.

## Why this project exists

Swimming results are often published in semi-structured formats that are hard to search, compare or analyze over time. SwimStats Chile turns those sources into normalized data so athletes, clubs and competitions can be explored with better traceability.

The current dataset focuses on Chilean master swimming results, especially public FCHMN result documents, but the product identity intentionally avoids depending on a single federation as its brand.

## Architecture overview

```mermaid
graph LR
    A[Public result sources] --> B[Scraper]
    B --> C[Manifest JSONL]
    C --> D[PDF downloader]
    D --> E[Parser and normalization]
    E --> F[Curated CSV materialization]
    F --> G[Batch validation gates]
    G --> H[(PostgreSQL staging)]
    H --> I[(PostgreSQL core)]
    I --> J[FastAPI]
    J --> K[React frontend]
```

## Monorepo structure

```text
backend/   Data ingestion pipeline, PostgreSQL schema, FastAPI endpoints and backend tests.
frontend/  React + TypeScript UI consuming API contracts and mock fixtures during integration.
docs/      Cross-project roadmap, plans and portfolio-level documentation.
```

Operational agent rules and tool-specific metadata may also live at the repository root when required by the development workflow.

## Tech stack

- **Backend:** Python, FastAPI, PostgreSQL, CLI pipelines.
- **Data processing:** PDF parsing, CSV materialization, staging/core loading, validation gates.
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query, Zod.
- **Documentation:** Markdown and Mermaid diagrams.

## Current status

This project is under active development.

Current focus:

- Auditable backend pipeline for historical result ingestion.
- Curated athlete and club identity handling before loading data into core tables.
- FastAPI endpoints for athletes, clubs and competition data.
- Frontend foundation with contract-first integration.

Planned:

- OpenAPI-based TypeScript generation from FastAPI contracts.
- Athlete and club profile pages.
- Competition result dashboards.
- Historical performance analysis and rankings.

## Subprojects

- [Backend documentation](backend/README.md)
- [Frontend documentation](frontend/README.md)
- [Implementation roadmap](docs/plans/implementation_plan.md)

## Data disclaimer

This project is intended for educational and portfolio purposes. Data sources may include publicly available swimming competition results. The repository does not represent an official federation platform, and raw/private data should not be committed to version control.
