# syntax=docker/dockerfile:1

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	MPLBACKEND=Agg

WORKDIR /app

# System packages for scientific stack may be needed; keeping minimal for now
# RUN apt-get update -y && apt-get install -y --no-install-recommends \
# 	build-essential \
# 	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
	python -m pip install -r requirements.txt

COPY . /app

EXPOSE 5000

# Ensure data dir exists (mounted in compose typically)
RUN mkdir -p /app/data/jira_sprint_processor

# Use gunicorn in production
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "web.server:app"]