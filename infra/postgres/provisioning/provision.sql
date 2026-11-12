SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L',
    :'app_user',
    :'app_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'app_user'
)
\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L',
    :'app_user',
    :'app_password'
)
\gexec

SELECT format(
    'CREATE DATABASE %I OWNER %I',
    :'app_db',
    :'app_user'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'app_db'
)
\gexec

SELECT format(
    'ALTER DATABASE %I OWNER TO %I',
    :'app_db',
    :'app_user'
)
\gexec
