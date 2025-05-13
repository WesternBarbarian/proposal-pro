
import click
from flask import current_app
from flask.cli import with_appcontext
from db.init_db import create_tables

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Initialize the database tables."""
    success = create_tables()
    if success:
        click.echo('Database tables initialized successfully.')
    else:
        click.echo('Failed to initialize database tables.')

def register_commands(app):
    """Register database commands with the Flask app."""
    app.cli.add_command(init_db_command)
