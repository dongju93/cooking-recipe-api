#!/bin/bash
set -e

uv run python src/manage.py wait_for_db
uv run python src/manage.py migrate
uv run python src/manage.py runserver 0.0.0.0:8080
