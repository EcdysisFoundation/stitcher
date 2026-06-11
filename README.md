# stitcher

The Stitcher FastAPI is used to allow creating panoramas from a scan of an overlapping grid of images taken by a 35mm digital camera. The api accepts a zipped directory of images, stitches them into a panorama and provides a database to keep track of information about these panoramas until they are related and saved to records in an external "Django" application. These images are stored locally up to that point. Among the information stored in the database are inference prediction results from our ultralytics repo (see https://github.com/EcdysisFoundation/ultralytics ) and annotations from label-studio. The intention of running the stitching application as a smaller, seperate application is to isolate the high level of computing resoruces required to stitch the images to our local hardware and to not impact the performance of our primary database application. Stitching jobs are sent to Celery. Monitoring available through Flower at localhost port 5557

# stitching
The stitching process uses code from https://github.com/OpenStitching/stitching which is based on OpenCV. Instead of installing from pypi, the code is in directory /stitching to allow for modifications and easier integration into FastAPI

## Docker

To start the app

    docker compose up -d

To see the console logs

    docker compose logs --tail=1000 --follow

## database

The SQLite database file (sqlite_data/database.db) is in a Docker volume. A blank database will be created when starting a volume, but this will be incompatible with any existing alembic files in the repo, so these should removed for new projects. SQLite does not support concurrent database writes, so additional databases may be needed, example see CELERY_DB_URL_URL in common.env

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

To undo a recent migration, run `alembic downgrade REVISION_ID` where REVISION_ID is the previous revsion_id to the one you want to remove. Then ensure the REVSION_ID is set as current in the database with `alembic current`, which should return the REVISION_ID. Finally, it is safe to delete the migration file.

## User Interface

We access the Stitcher API through a user interface integrated into an external Django project. See https://github.com/EcdysisFoundation/bugbox_open and views in urls under bugbox3.core.urls.
