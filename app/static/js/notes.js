"use strict";
(function () {
  let notes = pageData();
  const $ = (id) => document.getElementById(id);
  let current = null;
  let previewMode = true;

  // ---- minimal Markdown: input is escaped first, so the output is safe -------
  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function inline(s) {
    return s
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }
  function render(text) {
    const out = [];
    let list = false;
    const closeList = () => { if (list) { out.push("</ul>"); list = false; } };
    escapeHtml(text).split(/\r?\n/).forEach((line) => {
      const t = line.trim();
      let m;
      if (!t) { closeList(); return; }
      if ((m = t.match(/^(#{1,3})\s+(.*)/))) {
        closeList();
        const level = m[1].length + 1;
        out.push(`<h${level}>${inline(m[2])}</h${level}>`);
      } else if ((m = t.match(/^[-*]\s+(.*)/))) {
        if (!list) { out.push("<ul>"); list = true; }
        out.push(`<li>${inline(m[1])}</li>`);
      } else if ((m = t.match(/^&gt;\s?(.*)/))) {
        closeList();
        out.push(`<blockquote>${inline(m[1])}</blockquote>`);
      } else {
        closeList();
        out.push(`<p>${inline(t)}</p>`);
      }
    });
    closeList();
    return out.join("\n");
  }

  // ---- list and editor ----------------------------------------------------------
  function renderList() {
    const ul = $("note-list");
    ul.textContent = "";
    notes.forEach((n) => {
      const li = document.createElement("li");
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = n.title;
      if (current && current.id === n.id) b.setAttribute("aria-current", "true");
      b.addEventListener("click", () => open(n));
      li.append(b);
      ul.append(li);
    });
    $("note-empty").hidden = notes.length > 0;
    $("note-editor").hidden = !current;
  }

  function applyMode() {
    $("note-body").hidden = previewMode;
    $("note-preview").hidden = !previewMode;
    $("note-mode").textContent = previewMode ? "Редактировать" : "Просмотр";
    if (previewMode) $("note-preview").innerHTML = render(current.body);
  }

  function open(note) {
    flush();
    current = note;
    $("note-title").value = note.title;
    $("note-body").value = note.body;
    $("note-state").textContent = "";
    previewMode = Boolean(note.body.trim());
    applyMode();
    renderList();
  }

  // ---- saving -------------------------------------------------------------------
  let dirty = false;

  async function save() {
    if (!dirty || !current) return;
    dirty = false;
    const note = current;
    note.title = $("note-title").value;
    note.body = $("note-body").value;
    await api("/notes/" + note.id, "PATCH", { title: note.title, body: note.body });
    if (note === current) $("note-state").textContent = "Сохранено";
    renderList();
  }
  const autosave = debounce(save, 700);

  function flush() { if (dirty) save(); }

  function changed() {
    dirty = true;
    $("note-state").textContent = "Сохранение…";
    autosave();
  }
  $("note-title").addEventListener("input", changed);
  $("note-body").addEventListener("input", changed);
  window.addEventListener("pagehide", () => {
    if (!dirty || !current) return;
    fetch(window.API_ROOT + "/notes/" + current.id, {
      method: "PATCH", keepalive: true,
      headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF },
      body: JSON.stringify({ title: $("note-title").value, body: $("note-body").value }),
    });
  });

  $("note-mode").addEventListener("click", () => {
    current.body = $("note-body").value;
    previewMode = !previewMode;
    applyMode();
    if (!previewMode) $("note-body").focus();
  });

  $("note-new").addEventListener("click", async () => {
    flush();
    const note = await api("/notes", "POST", { title: "Новый конспект" });
    notes.unshift(note);
    open(note);
    previewMode = false;
    applyMode();
    $("note-title").select();
  });

  $("note-delete").addEventListener("click", async () => {
    if (!confirm("Удалить этот конспект?")) return;
    dirty = false;
    await api("/notes/" + current.id, "DELETE");
    notes = notes.filter((n) => n !== current);
    current = null;
    if (notes.length) open(notes[0]);
    else renderList();
  });

  // ---- tabs and highlight filter --------------------------------------------------
  function tab(showNotes) {
    $("pane-notes").hidden = !showNotes;
    $("pane-hl").hidden = showNotes;
    [["tab-notes", showNotes], ["tab-hl", !showNotes]].forEach(([id, on]) => {
      $(id).setAttribute("aria-selected", String(on));
      $(id).setAttribute("aria-pressed", String(on));
    });
  }
  $("tab-notes").addEventListener("click", () => tab(true));
  $("tab-hl").addEventListener("click", () => tab(false));

  document.querySelectorAll("#hl-filter button").forEach((b) => {
    b.addEventListener("click", () => {
      const color = b.dataset.color;
      document.querySelectorAll(".hl-list-full li").forEach((li) => {
        li.hidden = Boolean(color) && li.dataset.color !== color;
      });
      document.querySelectorAll(".hl-group").forEach((g) => {
        g.hidden = !g.querySelector("li:not([hidden])");
      });
      document.querySelectorAll("#hl-filter button").forEach((x) => x.classList.toggle("chip-solid", x === b));
    });
  });

  if (notes.length) open(notes[0]);
  else renderList();
})();
