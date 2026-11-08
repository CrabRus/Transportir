"""Pages and JSON API, all scoped to a subject by the URL."""
import json
import random

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, url_for)

from . import content, db
from .auth import login_required

root = Blueprint("root", __name__)
bp = Blueprint("subject", __name__, url_prefix="/s/<subject>")

COLORS = ("yellow", "green", "blue", "pink", "orange")
MAX_QUOTE = 8000
MAX_NOTE = 200_000
MAX_ANSWER = 30_000

SECTIONS = [
    ("article", "Статьи"),
    ("quiz", "Тесты"),
    ("open", "Открытые вопросы"),
    ("translation", "Карточки: перевод"),
    ("definition", "Карточки: определения"),
    ("matching", "Соответствия"),
]
SECTION_LABELS = dict(SECTIONS)
TRACKED_KINDS = set(SECTION_LABELS)


# ---- subject resolution ------------------------------------------------------

@bp.url_value_preprocessor
def _pull_subject(_endpoint, values):
    g.subject = content.subjects().get(values.pop("subject"))
    if g.subject is None:
        abort(404)


@bp.url_defaults
def _add_subject(endpoint, values):
    if "subject" not in values and getattr(g, "subject", None) is not None:
        if current_app.url_map.is_endpoint_expecting(endpoint, "subject"):
            values["subject"] = g.subject.slug


@bp.context_processor
def _subject_context():
    return {"subject": g.subject} if g.subject is not None else {}


def _section_stats(subject):
    done = db.mastered_counts(g.user["id"], subject.slug)
    stats = []
    for kind, label in SECTIONS:
        ids = subject.item_ids(kind)
        if ids:
            count = len(done.get(kind, set()) & ids)
            stats.append({"kind": kind, "label": label, "done": count, "total": len(ids),
                          "pct": round(100 * count / len(ids))})
    return stats


def _overall(stats):
    total = sum(s["total"] for s in stats)
    return round(100 * sum(s["done"] for s in stats) / total) if total else 0


# ---- site root ---------------------------------------------------------------

@root.route("/")
def index():
    subjects = list(content.subjects().values())
    if g.user is None:
        return render_template("landing.html", subjects=subjects)
    if len(subjects) == 1:
        return redirect(url_for("subject.dashboard", subject=subjects[0].slug))
    cards = [{"subject": s, "overall": _overall(_section_stats(s))} for s in subjects]
    return render_template("subjects.html", cards=cards)


# ---- pages -------------------------------------------------------------------

@bp.route("/")
@login_required
def dashboard():
    subject = g.subject
    stats = _section_stats(subject)
    read = db.progress_map(g.user["id"], subject.slug, "article")
    next_article = next(
        (a for a in subject.articles if a["slug"] not in read and not a["optional"]), None
    )
    attempts = db.get().execute(
        "SELECT * FROM attempts WHERE user_id=? AND subject=? AND kind='quiz'"
        " ORDER BY id DESC LIMIT 5",
        (g.user["id"], subject.slug),
    ).fetchall()
    return render_template(
        "dashboard.html", stats=stats, overall=_overall(stats),
        next_article=next_article, attempts=attempts, active="dashboard",
    )


@bp.route("/articles")
@login_required
def articles():
    subject = g.subject
    read = db.progress_map(g.user["id"], subject.slug, "article")
    groups = [
        {"topic": t, "items": [a for a in subject.articles if a["topic"] == t["slug"]]}
        for t in subject.topics_with(["article"])
    ]
    return render_template("articles.html", groups=groups, read=read, active="articles")


@bp.route("/articles/<slug>")
@login_required
def article(slug):
    subject = g.subject
    item = subject.article_by_slug.get(slug)
    if item is None:
        abort(404)
    conn = db.get()
    highlights = conn.execute(
        "SELECT id, start_offset, end_offset, quote, color FROM highlights"
        " WHERE user_id=? AND subject=? AND article=? ORDER BY start_offset",
        (g.user["id"], subject.slug, slug),
    ).fetchall()
    notes = conn.execute(
        "SELECT id, title, article FROM notes WHERE user_id=? AND subject=? ORDER BY updated_at DESC",
        (g.user["id"], subject.slug),
    ).fetchall()
    index_of = next(i for i, a in enumerate(subject.articles) if a["slug"] == slug)
    return render_template(
        "article.html", article=item, active="articles",
        highlights=[dict(h) for h in highlights],
        notes=[dict(n) for n in notes],
        is_read=slug in db.progress_map(g.user["id"], subject.slug, "article"),
        prev_article=subject.articles[index_of - 1] if index_of else None,
        next_article=subject.articles[index_of + 1] if index_of + 1 < len(subject.articles) else None,
        colors=COLORS,
        glossary=[{"term": c["term"], "translation": c["translation"]} for c in subject.glossary],
    )


@bp.route("/practice")
@login_required
def practice():
    stats = {s["kind"]: s for s in _section_stats(g.subject)}
    return render_template(
        "practice.html", stats=stats, active="practice",
        topics=g.subject.topics_with(["quiz", "translation", "definition"]),
    )


def _by_topic(items):
    topic = request.args.get("topic")
    return [i for i in items if i["topic"] == topic] if topic else list(items)


@bp.route("/practice/quiz")
@login_required
def quiz():
    items = _by_topic(g.subject.quiz)
    if request.args.get("mode") == "mistakes":
        progress = db.progress_map(g.user["id"], g.subject.slug, "quiz")
        items = [q for q in items if q["id"] in progress and not progress[q["id"]]["last_correct"]]
        if not items:
            flash("Ошибок для повторения нет — можно пройти обычный тест.", "info")
            return redirect(url_for("subject.practice"))
    if not items:
        abort(404)
    size = request.args.get("n", default=15, type=int)
    picked = random.sample(items, min(max(size, 1), len(items)))
    return render_template("quiz.html", questions=picked, active="practice")


def _cards(kind, items, title):
    if not items:
        abort(404)
    progress = db.progress_map(g.user["id"], g.subject.slug, kind)
    random.shuffle(items)
    items.sort(key=lambda c: progress[c["id"]]["box"] if c["id"] in progress else 0)
    return render_template("cards.html", cards=items, kind=kind, title=title, active="practice")


@bp.route("/practice/translation")
@login_required
def cards_translation():
    return _cards("translation", _by_topic(g.subject.glossary), "Карточки: перевод")


@bp.route("/practice/definitions")
@login_required
def cards_definition():
    return _cards("definition", _by_topic(g.subject.definitions), "Карточки: определения")


@bp.route("/practice/open")
@login_required
def open_list():
    answered = db.progress_map(g.user["id"], g.subject.slug, "open")
    groups = [
        {"topic": t, "items": [q for q in g.subject.open if q["topic"] == t["slug"]]}
        for t in g.subject.topics_with(["open"])
    ]
    return render_template("open_list.html", groups=groups, answered=answered, active="practice")


@bp.route("/practice/open/<qid>")
@login_required
def open_question(qid):
    question = g.subject.open_by_id.get(qid)
    if question is None:
        abort(404)
    saved = db.get().execute(
        "SELECT answer, checked FROM open_answers WHERE user_id=? AND subject=? AND question_id=?",
        (g.user["id"], g.subject.slug, qid),
    ).fetchone()
    return render_template(
        "open_question.html", q=question, active="practice",
        saved_answer=saved["answer"] if saved else "",
        saved_checked=json.loads(saved["checked"]) if saved else [],
        has_saved=saved is not None,
    )


@bp.route("/practice/matching")
@login_required
def matching_list():
    progress = db.progress_map(g.user["id"], g.subject.slug, "matching")
    groups = [
        {"topic": t, "items": [s for s in g.subject.matching if s["topic"] == t["slug"]]}
        for t in g.subject.topics_with(["matching"])
    ]
    return render_template("matching_list.html", groups=groups, progress=progress, active="practice")


@bp.route("/practice/matching/<set_id>")
@login_required
def matching(set_id):
    item = g.subject.matching_by_id.get(set_id)
    if item is None:
        abort(404)
    ids = [s["id"] for s in g.subject.matching]
    pos = ids.index(set_id)
    next_id = ids[pos + 1] if pos + 1 < len(ids) else None
    return render_template("matching.html", item=item, next_id=next_id, active="practice")


@bp.route("/glossary")
@login_required
def glossary():
    terms = sorted(g.subject.glossary, key=lambda c: c["term"].lower())
    return render_template(
        "glossary.html", terms=terms, topics=g.subject.topics_with(["translation"]), active="glossary"
    )


@bp.route("/notes")
@login_required
def notes():
    conn = db.get()
    uid, slug = g.user["id"], g.subject.slug
    note_rows = conn.execute(
        "SELECT * FROM notes WHERE user_id=? AND subject=? ORDER BY updated_at DESC", (uid, slug)
    ).fetchall()
    rows = conn.execute(
        "SELECT * FROM highlights WHERE user_id=? AND subject=? ORDER BY article, start_offset",
        (uid, slug),
    ).fetchall()
    by_article = {}
    for row in rows:
        by_article.setdefault(row["article"], []).append(dict(row))
    groups = [
        {"article": a, "items": by_article[a["slug"]]}
        for a in g.subject.articles if a["slug"] in by_article
    ]
    return render_template(
        "notes.html", notes=[dict(n) for n in note_rows], groups=groups,
        colors=COLORS, active="notes",
    )


# ---- JSON API ----------------------------------------------------------------

def _payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    return data


def _uid_slug():
    return g.user["id"], g.subject.slug


@bp.route("/api/progress", methods=["POST"])
@login_required
def api_progress():
    data = _payload()
    kind = data.get("kind")
    if kind not in TRACKED_KINDS:
        abort(400)
    uid, slug = _uid_slug()
    known = g.subject.item_ids(kind)
    results = [
        (r["id"], bool(r.get("correct")))
        for r in data.get("results", [])
        if isinstance(r, dict) and r.get("id") in known
    ]
    if results:
        db.record_results(uid, slug, kind, results)
    attempt = data.get("attempt")
    if isinstance(attempt, dict):
        score, total = attempt.get("score"), attempt.get("total")
        if isinstance(score, int) and isinstance(total, int) and 0 <= score <= total and total > 0:
            db.add_attempt(uid, slug, kind, score, total)
    return jsonify(ok=True)


@bp.route("/api/open/<qid>", methods=["POST"])
@login_required
def api_open(qid):
    question = g.subject.open_by_id.get(qid)
    if question is None:
        abort(404)
    data = _payload()
    answer = str(data.get("answer", ""))[:MAX_ANSWER]
    points = len(question["key_points"])
    raw = data.get("checked", [])
    checked = sorted({i for i in raw if isinstance(i, int) and 0 <= i < points}) if isinstance(raw, list) else []
    uid, slug = _uid_slug()
    conn = db.get()
    conn.execute(
        """INSERT INTO open_answers (user_id, subject, question_id, answer, checked, updated_at)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT (user_id, subject, question_id) DO UPDATE SET
             answer=excluded.answer, checked=excluded.checked, updated_at=excluded.updated_at""",
        (uid, slug, qid, answer, json.dumps(checked), db.now()),
    )
    conn.commit()
    if data.get("final"):
        db.record_results(uid, slug, "open", [(qid, True)])
    return jsonify(ok=True)


@bp.route("/api/highlights", methods=["POST"])
@login_required
def api_highlight_create():
    data = _payload()
    article_slug, start, end, color = (data.get(k) for k in ("article", "start", "end", "color"))
    quote = data.get("quote")
    if (article_slug not in g.subject.article_by_slug or color not in COLORS
            or not isinstance(start, int) or not isinstance(end, int)
            or not 0 <= start < end or not isinstance(quote, str)
            or not quote or len(quote) > MAX_QUOTE):
        abort(400)
    uid, slug = _uid_slug()
    conn = db.get()
    cur = conn.execute(
        "INSERT INTO highlights (user_id, subject, article, start_offset, end_offset, quote, color, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (uid, slug, article_slug, start, end, quote, color, db.now()),
    )
    conn.commit()
    return jsonify(id=cur.lastrowid)


@bp.route("/api/highlights/<int:hid>", methods=["PATCH", "DELETE"])
@login_required
def api_highlight_change(hid):
    uid, slug = _uid_slug()
    conn = db.get()
    if request.method == "DELETE":
        conn.execute("DELETE FROM highlights WHERE id=? AND user_id=? AND subject=?", (hid, uid, slug))
    else:
        color = _payload().get("color")
        if color not in COLORS:
            abort(400)
        conn.execute("UPDATE highlights SET color=? WHERE id=? AND user_id=? AND subject=?", (color, hid, uid, slug))
    conn.commit()
    return jsonify(ok=True)


def _note_json(row):
    return {k: row[k] for k in ("id", "title", "body", "article", "updated_at")}


def _get_note(note_id):
    uid, slug = _uid_slug()
    return db.get().execute(
        "SELECT * FROM notes WHERE id=? AND user_id=? AND subject=?", (note_id, uid, slug)
    ).fetchone()


def _create_note(title, body="", article_slug=None):
    uid, slug = _uid_slug()
    stamp = db.now()
    cur = db.get().execute(
        "INSERT INTO notes (user_id, subject, article, title, body, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (uid, slug, article_slug, title[:200], body[:MAX_NOTE], stamp, stamp),
    )
    db.get().commit()
    return _get_note(cur.lastrowid)


@bp.route("/api/notes", methods=["POST"])
@login_required
def api_note_create():
    title = str(_payload().get("title") or "Новый конспект").strip() or "Новый конспект"
    return jsonify(_note_json(_create_note(title)))


@bp.route("/api/notes/<int:note_id>", methods=["PATCH", "DELETE"])
@login_required
def api_note_change(note_id):
    if _get_note(note_id) is None:
        abort(404)
    conn = db.get()
    if request.method == "DELETE":
        conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        conn.commit()
        return jsonify(ok=True)
    data = _payload()
    if "title" in data:
        conn.execute("UPDATE notes SET title=? WHERE id=?",
                     (str(data["title"]).strip()[:200] or "Без названия", note_id))
    if "body" in data:
        conn.execute("UPDATE notes SET body=? WHERE id=?", (str(data["body"])[:MAX_NOTE], note_id))
    conn.execute("UPDATE notes SET updated_at=? WHERE id=?", (db.now(), note_id))
    conn.commit()
    return jsonify(_note_json(_get_note(note_id)))


@bp.route("/api/notes/clip", methods=["POST"])
@login_required
def api_note_clip():
    """Append a quote from an article to a note."""
    data = _payload()
    article_item = g.subject.article_by_slug.get(data.get("article"))
    quote = " ".join(str(data.get("quote", "")).split())[:MAX_QUOTE]
    if article_item is None or not quote:
        abort(400)
    note = _get_note(data["note_id"]) if isinstance(data.get("note_id"), int) else None
    if note is None:
        uid, slug = _uid_slug()
        note = db.get().execute(
            "SELECT * FROM notes WHERE user_id=? AND subject=? AND article=? ORDER BY id LIMIT 1",
            (uid, slug, article_item["slug"]),
        ).fetchone() or _create_note(article_item["title"], article_slug=article_item["slug"])
    addition = f"> {quote}\n\n— *{article_item['title']}*\n"
    body = f"{note['body'].rstrip()}\n\n{addition}" if note["body"].strip() else addition
    conn = db.get()
    conn.execute("UPDATE notes SET body=?, updated_at=? WHERE id=?", (body[:MAX_NOTE], db.now(), note["id"]))
    conn.commit()
    return jsonify(_note_json(_get_note(note["id"])))
