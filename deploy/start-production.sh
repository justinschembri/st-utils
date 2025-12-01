#!/bin/sh
# startup the full production stack
docker compose \
-p st-utils-production \
-f ./docker-compose.base.yml \
-f ./docker-compose.auth.yml \
-f ./docker-compose.persistent.yml \
-f ./docker-compose.app.yml \
up -d
