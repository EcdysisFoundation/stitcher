# stitcher

# stitching
The stitching process uses code from https://github.com/OpenStitching/stitching . Instead of installing theirs from pypi, the code is in directory /stitching to allow for modifications and easier integration into FastAPI

## Docker

To start the app

    docker compose up -d

To see the console logs

    docker compose logs --tail=1000 --follow

## database

The SQLite database file (data/database.db) is in a Docker volume. A blank database will be created when starting a volume, but this will be incompatible with any existing alembic files in the repo. Replacing the data/database.db file with a copy of the production database will make it compatible with the migration files.

### migrations

We use Alembic to manage database migrations. To use Alembic, we need to run the commands through the docker container. Run MY_STATEMENT in a docker container by finding the CONTAINER_ID with `docker ps` then execute like `docker exec -it CONTAINER_ID sh -c "MY_STATEMENT"`.

To check the state of Alembic, run the following command. All other alembic commands need to be ran in the same way, where the alembic command `check` is replaced with the other alembic commands.

    docker exec -it CONTAINER_ID sh -c "alembic --config app/alembic.ini check"

To add a column to a model, for example

    alembic revision --autogenerate -m "added my column"

when through docker, it is written,

    docker exec -it CONTAINER_ID sh -c "alembic --config app/alembic.ini revision --autogenerate -m "added my column""

Review the generated migraitons file, then run this command

    alembic upgrade head

To undo a recent migration, run `alembic downgrade REVISION_ID` and then delete the migration file.
