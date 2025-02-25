# Makefile
.PHONY: server-start worker-start

server-start:
	@echo "Starting Prefect server..."
	prefect server start

worker-start:
	@echo "Starting Prefect worker..."
	prefect worker start --pool "my-pool"

clean-db:
	@echo "Cleaning server artifacts..."
	rm -rf ~/.prefect/prefect.db

clean-start: clean-db server-start

all: server-start worker-start
