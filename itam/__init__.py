import os

from flask import Flask

from .models import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    # Use DATABASE_URL only when it is a real connection URL; some hosts
    # pre-set it to a placeholder string.
    database_url = os.environ.get("DATABASE_URL", "")
    if "://" not in database_url:
        database_url = "sqlite:///" + os.path.join(app.instance_path, "itam.sqlite")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=database_url,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    from . import routes

    app.register_blueprint(routes.bp)

    with app.app_context():
        db.create_all()

    @app.cli.command("seed")
    def seed_command():
        """Populate the database with sample data."""
        from .seed import seed

        seed()
        print("Database seeded.")

    return app
