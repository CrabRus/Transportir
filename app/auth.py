"""Registration, login and the admin password reset command."""
import functools
import re
import sqlite3
import time

import click
from flask import (Blueprint, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[\w.-]{3,32}$")
MIN_PASSWORD = 6
MAX_FAILURES = 8
LOCK_SECONDS = 15 * 60


def init_app(app):
    app.before_request(_load_user)

    @app.cli.command("reset-password")
    @click.argument("username")
    @click.password_option()
    def reset_password(username, password):
        """Set a new password for USERNAME."""
        conn = db.get()
        cur = conn.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (generate_password_hash(password), username),
        )
        conn.commit()
        click.echo("Пароль обновлён." if cur.rowcount else "Пользователь не найден.")


def _load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = db.get().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if "/api/" in request.path:
                return jsonify(error="login required"), 401
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def _safe_next(target):
    if target and target.startswith("/") and not target.startswith(("//", "/\\")):
        return target
    return url_for("root.index")


def _start_session(user_id):
    token = session.get("csrf")
    session.clear()
    if token:
        session["csrf"] = token
    session["user_id"] = user_id
    session.permanent = True


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("root.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not USERNAME_RE.match(username):
            flash("Логин: от 3 до 32 символов — буквы, цифры, точка, дефис или подчёркивание.", "error")
        elif len(password) < MIN_PASSWORD:
            flash(f"Пароль должен быть не короче {MIN_PASSWORD} символов.", "error")
        elif password != request.form.get("password2", ""):
            flash("Пароли не совпадают.", "error")
        else:
            conn = db.get()
            try:
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                    (username, generate_password_hash(password), db.now()),
                )
            except sqlite3.IntegrityError:
                flash("Такой логин уже занят.", "error")
            else:
                conn.commit()
                _start_session(cur.lastrowid)
                return redirect(url_for("root.index"))
    return render_template("auth.html", mode="register")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("root.index"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = db.get()
        since = time.time() - LOCK_SECONDS
        conn.execute("DELETE FROM login_failures WHERE at < ?", (since,))
        failures = conn.execute(
            "SELECT COUNT(*) FROM login_failures WHERE username=?", (username,)
        ).fetchone()[0]
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if failures >= MAX_FAILURES:
            conn.commit()
            flash("Слишком много попыток входа. Попробуйте через 15 минут.", "error")
        elif user and check_password_hash(user["password_hash"], password):
            conn.execute("DELETE FROM login_failures WHERE username=?", (username,))
            conn.commit()
            _start_session(user["id"])
            return redirect(_safe_next(request.args.get("next")))
        else:
            conn.execute("INSERT INTO login_failures (username, at) VALUES (?,?)", (username, time.time()))
            conn.commit()
            flash("Неверный логин или пароль.", "error")
    return render_template("auth.html", mode="login")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("root.index"))
