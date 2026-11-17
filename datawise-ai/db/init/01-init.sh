#!/bin/sh
# Runs once, on first start of an empty Postgres volume (docker-entrypoint-initdb.d).
# Creates the two databases and the read-only analytics role.
set -eu

: "${DATAWISE_READER_PASSWORD:?DATAWISE_READER_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<EOSQL
CREATE DATABASE datawise_app;
CREATE DATABASE datawise_analytics;
CREATE ROLE datawise_reader LOGIN PASSWORD '${DATAWISE_READER_PASSWORD}';
ALTER ROLE datawise_reader SET default_transaction_read_only = on;
ALTER ROLE datawise_reader SET statement_timeout = '10s';
REVOKE ALL ON DATABASE datawise_app FROM PUBLIC;
REVOKE ALL ON DATABASE datawise_analytics FROM PUBLIC;
GRANT CONNECT ON DATABASE datawise_analytics TO datawise_reader;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname datawise_analytics <<EOSQL
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO datawise_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE "${POSTGRES_USER}" IN SCHEMA public GRANT SELECT ON TABLES TO datawise_reader;
EOSQL
