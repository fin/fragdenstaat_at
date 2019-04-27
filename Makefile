COMPOSE=docker-compose
DEVDOCKER=$(COMPOSE) run --rm backend

all: setup migrate web

services:
	$(COMPOSE) up -d db elasticsearch

shell: services
	$(DEVDOCKER) /bin/bash

migrate: build services
	$(DEVDOCKER) python manage.py migrate --noinput

web: services
	$(COMPOSE) up backend

stop:
	$(COMPOSE) down
	$(COMPOSE) rm -f

clean:
	rm -rf dist build .eggs
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +

setup: docker_baseimage docker_elasticsearch
	./devsetup.sh
	$(COMPOSE) build

resetup:
	./devsetup.sh
	$(COMPOSE) build --no-cache

build:
	$(COMPOSE) stop backend
	$(DEVDOCKER) npm run build

docker_baseimage: Dockerfile.fragdenstaat_at-baseimage requirements-dev.txt requirements.txt
	docker build -f Dockerfile.fragdenstaat_at-baseimage . -t fragdenstaat_at-baseimage

docker_elasticsearch: Dockerfile.fragdenstaat_at-elasticsearch
	docker build -f Dockerfile.fragdenstaat_at-elasticsearch . -t fragdenstaat_at-elasticsearch



resetup_dockerimages: docker_baseimage_force docker_elasticsearch_force

docker_baseimage_force:
	docker build -f Dockerfile.fragdenstaat_at-baseimage . -t fragdenstaat_at-baseimage

docker_elasticsearch_force:
	docker build -f Dockerfile.fragdenstaat_at-elasticsearch . -t fragdenstaat_at-elasticsearch


.PHONY: build docker_baseimage_force docker_elasticsearch_force
