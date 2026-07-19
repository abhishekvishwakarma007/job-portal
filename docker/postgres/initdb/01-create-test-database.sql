-- Creates the dedicated test database alongside the application one.
--
-- The suite truncates every table between tests, so it must never point at the
-- database holding development data. Provisioning it here rather than in a
-- README step keeps `docker compose up` the only command anyone has to run,
-- and stops the test fixture from silently skipping the whole suite when the
-- database it expects is absent.
--
-- Postgres runs files in /docker-entrypoint-initdb.d/ only when the data
-- directory is empty, i.e. on first boot of the named volume. The \gexec guard
-- keeps the script harmless if it is ever replayed by hand -- CREATE DATABASE
-- has no IF NOT EXISTS form.
SELECT 'CREATE DATABASE jobportal_test OWNER jobportal'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'jobportal_test'
)\gexec
