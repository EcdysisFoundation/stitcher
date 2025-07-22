# stitcher

## database

The SQLite database file (data/database.db) is in a Docker volume.

### migrations

We use Alembic to manage database migrations. To add a column to a model, change the model then run inside docker container, for example

    alembic revision --autogenerate -m "added my column"

Review the generated migraitons file, then run it with

    alembic upgrade head

To undo the most recent migration, run `alembic downgrade -1` and then delete the migration file.
