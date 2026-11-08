"""Application factory."""
import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, abort, render_template, request, session

from . import auth, content, db, views

BASE_DIR = Path(__file__).resolve().parent.parent
SITE_NAME = "Transportir"


def _load_secret_key(instance_dir):
    """Use SECRET_KEY from the environment, or create one kept on disk."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = instance_dir / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="ascii")
    return path.read_text(encoding="ascii").strip()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def create_app(content_dir=None, instance_dir=None):
    instance = Path(instance_dir or BASE_DIR / "instance")
    instance.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=_load_secret_key(instance),
        DATABASE=str(instance / "app.db"),
        CONTENT_DIR=str(content_dir or BASE_DIR / "content"),
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.environ.get("HTTPS_ONLY") == "1",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SITE_NAME=os.environ.get("SITE_NAME", SITE_NAME),
    )

    db.init_app(app)
    content.init_app(app)
    auth.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(views.root)
    app.register_blueprint(views.bp)

    @app.before_request
    def _check_csrf():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, description="CSRF token missing or invalid")

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.errorhandler(404)
    def _not_found(_error):
        return render_template("error.html", code=404, message="Такой страницы нет."), 404

    @app.context_processor
    def _inject():
        return {"csrf_token": csrf_token, "site_name": app.config["SITE_NAME"]}

    return app
