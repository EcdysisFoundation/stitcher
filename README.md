# stitcher

# stitching
The stitching process uses code from https://github.com/OpenStitching/stitching . Instead of installing from pypi, the code is in directory /stitching to allow for modifications and easier integration into FastAPI

## Docker

To start the app

    docker compose up -d

To see the console logs

    docker compose logs --tail=1000 --follow

## database

The SQLite database file (data/database.db) is in a Docker volume. A blank database will be created when starting a volume, but this will be incompatible with any existing alembic files in the repo. On a development machine, or new deployment, the data/database.db file with a copy of the production database will make the database compatible with the migration files to use the repo as is.

There are no automated database backup configured at this time. It is intended that data gets worked through the Stitcher system, then gets entered into the Bugbox database where there is a backup strategy. Do a manual backup before any significant changes that present risk to the database.

To get a database backup. With the docker container running on production system, get the CONTAINER_ID with `docker ps`.

`docker cp CONTAINER_ID:/data/database.db database.db` to copy the db to the current directory.

On local machine, copy it down `scp ecdysis@ecdysis01.local:/srv/stitcher/database.db database.db`

With the container running locally, get the id with `docker ps`

Copy the db to it with docker `docker cp database.db CONTAINER_ID:/data/database.db` and restart the container.

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

## User Interface

The UI is in bugbox, intended to work on local Ecdysis01 server.
See https://github.com/EcdysisFoundation/bugbox3/tree/main/bugbox3/core for files `stitcher_x.py` and
https://github.com/EcdysisFoundation/bugbox3/tree/main/bugbox3/templates/core for files `stitcher_x.html` and
https://github.com/EcdysisFoundation/bugbox3/tree/main/bugbox3/static/js for `stitcher.js` and `stitcher_form.js`
