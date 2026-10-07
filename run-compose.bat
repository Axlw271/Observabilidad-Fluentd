@echo off
cd /d C:\Users\METIC\Documents\GitHub\Observabilidad-Fluentd
docker compose up --build -d >> run-compose.log 2>&1