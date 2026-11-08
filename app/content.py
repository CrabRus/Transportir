"""Loads course content from files.

Each folder in content/ containing a subject.json is a subject. Every other
file is optional: a section without content simply is not shown.

    content/<slug>/subject.json
    content/<slug>/articles/*.md     (front matter + Markdown, sorted by name)
    content/<slug>/quiz.json         multiple-choice questions
    content/<slug>/open.json         open-answer questions
    content/<slug>/definitions.json  definition flashcards
    content/<slug>/glossary.json     dictionary, also feeds translation cards
    content/<slug>/matching.json     matching sets
"""
import json
import re
from pathlib import Path

import markdown as md
from flask import current_app
from markupsafe import escape

WORDS_PER_MINUTE = 180


class ContentError(Exception):
    pass


class Subject:
    def __init__(self, folder):
        self.folder = Path(folder)
        meta = self._json("subject.json")
        if meta is None:
            raise ContentError(f"{folder}: subject.json is missing")
        self.slug = self.folder.name
        self.title = meta["title"]
        self.title_ru = meta.get("title_ru", self.title)
        self.description = meta.get("description", "")
        self.order = meta.get("order", 100)
        self.topics = meta.get("topics", [])
        self.articles = self._load_articles()
        self.article_by_slug = {a["slug"]: a for a in self.articles}
        self.quiz = self._json("quiz.json") or []
        self.open = self._json("open.json") or []
        self.definitions = self._json("definitions.json") or []
        self.glossary = self._json("glossary.json") or []
        self.matching = self._json("matching.json") or []
        self.open_by_id = {q["id"]: q for q in self.open}
        self.matching_by_id = {s["id"]: s for s in self.matching}
        self._validate()

    def _json(self, name):
        path = self.folder / name
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContentError(f"{path}: {exc}") from exc

    def _load_articles(self):
        folder = self.folder / "articles"
        if not folder.is_dir():
            return []
        articles = []
        for path in sorted(folder.glob("*.md")):
            meta, body = _parse_front_matter(path)
            slug = re.sub(r"^\d+[-_]", "", path.stem)
            articles.append(
                {
                    "slug": slug,
                    "title": meta["title"],
                    "title_ru": meta.get("title_ru", ""),
                    "topic": meta["topic"],
                    "summary": meta.get("summary", ""),
                    "source": meta.get("source", ""),
                    "optional": meta.get("optional", "").lower() == "true",
                    "minutes": max(1, round(len(body.split()) / WORDS_PER_MINUTE)),
                    "html": _render_article(body),
                }
            )
        return articles

    def items(self, kind):
        return {
            "article": self.articles,
            "quiz": self.quiz,
            "open": self.open,
            "definition": self.definitions,
            "translation": self.glossary,
            "matching": self.matching,
        }.get(kind, [])

    def item_ids(self, kind):
        key = "slug" if kind == "article" else "id"
        return {item[key] for item in self.items(kind)}

    def topic_title(self, slug):
        for topic in self.topics:
            if topic["slug"] == slug:
                return topic.get("title_ru") or topic["title"]
        return slug

    def topics_with(self, kinds):
        used = {item["topic"] for kind in kinds for item in self.items(kind)}
        return [t for t in self.topics if t["slug"] in used]

    def _validate(self):
        topics = {t["slug"] for t in self.topics}
        for kind in ("article", "quiz", "open", "definition", "translation", "matching"):
            key = "slug" if kind == "article" else "id"
            seen = set()
            for item in self.items(kind):
                ident = item[key]
                if ident in seen:
                    raise ContentError(f"{self.slug}: duplicate {kind} id {ident!r}")
                seen.add(ident)
                if item["topic"] not in topics:
                    raise ContentError(f"{self.slug}: {ident!r} has unknown topic {item['topic']!r}")
        for q in self.quiz:
            if not 0 <= q["answer"] < len(q["options"]):
                raise ContentError(f"{self.slug}: quiz {q['id']!r} answer out of range")
        for card in self.glossary:
            for field in ("term", "translation", "meaning_en", "meaning_ru"):
                if not card.get(field):
                    raise ContentError(f"{self.slug}: glossary {card['id']!r} lacks {field}")
        for item in self.matching:
            rights = [pair[1] for pair in item["pairs"]]
            if len(set(rights)) != len(rights):
                raise ContentError(f"{self.slug}: matching {item['id']!r} repeats an answer")


# Articles are laid out like SQA marking instructions. A question starts with
#     ## 1 (a) | Explain | 6
# followed by Markdown for the detailed column.
QUESTION_RE = re.compile(r"^## ([^|\n]+?) \| (Describe|Explain|Evaluate|Analyse) \| (\d+)[ \t]*$", re.M)
COMMAND_GUIDANCE = {
    "Describe": "**Describe:** give the characteristics or features of something, in more depth than a list. Make a point, then develop it.",
    "Explain": "**Explain:** show cause and effect, or make clear how things are related.",
    "Evaluate": "**Evaluate:** judge the value of something against criteria. State the criterion, then say why it makes a strength or weakness.",
    "Analyse": "**Analyse:** identify the parts and how they relate to each other and to the whole, and draw out implications.\n\nAnalysis marks can come from:\n\n- implications\n- links to concepts, theories or studies\n- implications of strengths or weaknesses\n- applications",
}
MD_EXTENSIONS = ["tables", "sane_lists"]
RESPONSE_FOOTER = "You may give credit for research evidence.\n\n**Or any other relevant response.**"


def _md(text):
    return md.markdown(text, extensions=MD_EXTENSIONS)


def _render_article(body):
    parts = QUESTION_RE.split(body)
    if len(parts) == 1:
        return _md(body)
    rows = []
    for i in range(1, len(parts), 4):
        number, command, marks, detail = parts[i:i + 4]
        rows.append(
            '<div class="mi-row" role="row">'
            f'<div class="mi-q" role="cell">{escape(number)}</div>'
            f'<div class="mi-general" role="cell">{_md(COMMAND_GUIDANCE[command])}</div>'
            f'<div class="mi-max" role="cell">{marks}</div>'
            f'<div class="mi-detail" role="cell">{_md(detail.strip() + chr(10) * 2 + RESPONSE_FOOTER)}</div>'
            "</div>"
        )
    header = (
        '<div class="mi-row mi-head" role="row">'
        '<div role="columnheader">Question</div>'
        '<div role="columnheader">General marking instructions for this type of question</div>'
        '<div role="columnheader">Max mark</div>'
        '<div role="columnheader">Detailed marking instructions for this question</div>'
        "</div>"
    )
    return f'{_md(parts[0])}<div class="mi" role="table">{header}{"".join(rows)}</div>'


def _parse_front_matter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)", text, re.S)
    if not match:
        raise ContentError(f"{path}: front matter is missing")
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    for required in ("title", "topic"):
        if required not in meta:
            raise ContentError(f"{path}: front matter lacks {required!r}")
    return meta, match.group(2)


def load_subjects(content_dir):
    subjects = {}
    root = Path(content_dir)
    if root.is_dir():
        for folder in sorted(root.iterdir()):
            if (folder / "subject.json").exists():
                subjects[folder.name] = Subject(folder)
    return dict(sorted(subjects.items(), key=lambda kv: (kv[1].order, kv[1].title)))


def init_app(app):
    app.extensions["subjects"] = load_subjects(app.config["CONTENT_DIR"])


def subjects():
    return current_app.extensions["subjects"]
