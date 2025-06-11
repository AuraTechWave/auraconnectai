#!/bin/bash
echo "Setting up AuraConnect..."
cp ./env/.env.dev .env
docker-compose up --build -d
docker-compose ps
