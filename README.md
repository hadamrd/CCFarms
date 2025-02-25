# install prefect in venv
python -m venv prefect-env
source prefect-env/bin/activate
pip install -U prefect

# start server
prefect server start 
export PREFECT_API_URL=http://127.0.0.1:4200/api

# create a worker pool
prefect worker start --pool "my-pool"


# Create a secret block through the UI
prefect block create secret

# Register and create a custom block for teams notifications
prefect block register -m orchestration_play.blocks => to register block types defined in the project blocks
prefect block create teams-webhook => to get webui url to create a new block of the registred type

