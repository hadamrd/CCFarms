# start local quick setup
# install prefect in venv
poetry install

## start server
prefect server start 
export PREFECT_API_URL=http://127.0.0.1:4200/api
there is also
prefect config set PREFECT_API_URL=http://localhost:4200/api

## create a worker pool
prefect worker start --pool "default-pool"

# start interesting docker compose setup
docker compose up -d

# Create a secret block through the UI
prefect block create secret

# Register and create a custom block for teams notifications
prefect block register -m orchestration_play.blocks => to register block types defined in the project blocks
prefect block create teams-webhook => to get webui url to create a new block of the registred type

