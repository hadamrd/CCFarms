# Orchestration Play: AI-Powered News Analysis Pipeline

A sophisticated workflow automation system built with Prefect that analyzes news articles, identifies comedy potential, and generates satirical content using AI.

## Overview

This project implements a complete ETL pipeline that:

1. Collects news articles from various sources
2. Analyzes their content for comedy potential
3. Generates detailed satirical briefs
4. Creates polished comedy scripts based on the most promising articles
5. Stores results and notifies team members

The system leverages Claude 3.5 Sonnet for intelligent content analysis and creative generation, with all processes orchestrated through Prefect workflows.

## Prerequisites

- Python 3.10+
- Poetry
- Docker and Docker Compose
- Anthropic API key (for Claude)
- NewsAPI key (for article collection)
- Microsoft Teams webhook URL (optional, for notifications)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/hadamrd/prefect-playground.git
cd prefect-playground
```

### 2. Install Dependencies

```bash
# Create virtual environment and install dependencies
poetry install
```

### 3. Start the Infrastructure

```bash
# Launch the complete stack with MongoDB, Prefect server and worker
docker compose up -d

# Wait for all services to be healthy
docker compose ps
```

### 4. Set Up Environment

```bash
# Configure Prefect API URL for local client
export PREFECT_API_URL=http://127.0.0.1:4200/api
# OR permanently configure using:
# prefect config set PREFECT_API_URL=http://localhost:4200/api
```

### 5. Create Required Blocks

```bash
# Register custom blocks
prefect block register -m orchestration_play.blocks

# Create necessary configurations through the UI (http://localhost:4200)
# - Create a Secret block for Anthropic API key
prefect block create secret

# - Create NewsAPI configuration
prefect block create newsapi-config

# - Configure Teams webhook (optional)
prefect block create teams-webhook
```

### 6. Deploy Flows

```bash
# Deploy all flows to the Prefect server
prefect deploy --all
```

## Architecture

The project consists of several interconnected flows:

- **News Scoring Flow**: Collects and evaluates articles for comedy potential
- **Debriefer Flow**: Performs in-depth analysis on top articles
- **Comedy Script Flow**: Generates satirical scripts based on analyzed articles
- **Weather Flow**: Example flow with creative AI enhancements

All data is stored in MongoDB, with workflows orchestrated through Prefect and notifications delivered via Microsoft Teams.

## Key Components

### Agents

- **Debriefer**: Analyzes articles for comedy potential, absurdity, and cultural relevance
- **Satirist**: Transforms analyzed articles into witty comedy scripts

### Storage

- **ArticleCache**: Stores collected news articles
- **BriefStorage**: Manages detailed article analyses
- **ScriptStorage**: Archives generated comedy scripts

### Blocks

Custom Prefect blocks implement the following functionality:

- **NewsAPIBlock**: Configures and manages the NewsAPI client
- **ArticleCacheBlock**: Provides access to the article cache
- **BriefStorageBlock**: Configures brief storage settings
- **ScriptStorageBlock**: Manages script storage
- **TeamsWebhook**: Sends notifications to Microsoft Teams

## Development

### Project Structure

```
orchestration-play/
├── src/
│   └── orchestration_play/
│       ├── agents/
│       │   ├── debriefer/
│       │   └── satirist/
│       ├── blocks/
│       ├── clients/
│       ├── flows/
│       └── persistence/
├── prefect.yaml
├── pyproject.toml
└── docker-compose.yml
```

### Running Tests

```bash
poetry run pytest
```

### Type Checking

```bash
poetry run mypy
```

## Configuration

### Docker Compose

The `docker-compose.yml` file sets up:

- PostgreSQL for Prefect metadata
- Redis for Prefect task queues
- Prefect server for workflow orchestration
- Prefect worker for task execution
- MongoDB for article and analysis storage

### Prefect Deployments

The `prefect.yaml` file defines all deployable flows:

- `weather-flow`: Weather reporting with AI enhancements
- `news-scoring-flow`: Article collection and evaluation
- `comedy-brief-analysis`: Detailed comedy potential analysis
- `satire-script-generation`: Satirical script creation

## Managing Flows

### Running Flows

```bash
# Run flow from the CLI
prefect deployment run satire-script-generation/1.0.0

# Or schedule through the Prefect UI
```

### Monitoring

Access the Prefect dashboard at http://localhost:4200 to:

- Monitor flow runs
- View task status
- Examine flow logs
- Access generated artifacts

## Viewing Results

The Comedy Script Flow generates two types of artifacts:

1. A Markdown document with the formatted script
2. A link to the MongoDB document for database access

Both artifacts are accessible through the Prefect UI after a successful flow run.

## Troubleshooting

### Common Issues

- **Database Connection Errors**: Ensure MongoDB is running and credentials are correct
- **API Limits**: Check NewsAPI quotas if article collection fails
- **Worker Connection**: Verify Prefect worker is connected to the server
- **Type Checking Errors**: Mypy configuration in pyproject.toml can be adjusted

### Logs

```bash
# View container logs
docker compose logs -f prefect-worker

# View Prefect logs via UI or CLI
prefect deployment logs satire-script-generation/latest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.