"use strict";
(function () {
  const data = pageData();
  const root = document.getElementById("article-body");
  const toolbar = document.getElementById("hl-toolbar");
  const lookup = document.getElementById("hl-lookup");
  const delBtn = document.getElementById("hl-delete");
  const list = document.getElementById("hl-list");
  const empty = document.getElementById("hl-empty");
  const glossary = new Map(data.glossary.map((g) => [g.term.toLowerCase(), g.translation]));

  let highlights = [];
  let pending = null;   // {start, end, text} of the current selection
  let activeId = null;  // id of the highlight being edited

  // ---- offsets are measured in the article's plain text ----------------------

  function textNodes() {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    return nodes;
  }

  function resolve(h) {
    // The stored quote lets a highlight survive edits to the article text.
    const text = root.textContent;
    if (text.slice(h.start_offset, h.end_offset) === h.quote) return h;
    const at = text.indexOf(h.quote);
    return at < 0 ? null : { ...h, start_offset: at, end_offset: at + h.quote.length };
  }

  function paint(h) {
    let pos = 0;
    for (const node of textNodes()) {
      const from = pos;
      const to = pos + node.length;
      pos = to;
      if (to <= h.start_offset || from >= h.end_offset) continue;
      if (!node.data.trim()) continue;
      const a = Math.max(h.start_offset, from) - from;
      const b = Math.min(h.end_offset, to) - from;
      let target = node;
      if (a > 0) target = target.splitText(a);
      if (b - a < target.length) target.splitText(b - a);
      const mark = document.createElement("mark");
      mark.className = "m-" + h.color;
      mark.dataset.id = h.id;
      target.parentNode.insertBefore(mark, target);
      mark.appendChild(target);
    }
  }

  function marksOf(id) {
    return [...root.querySelectorAll(`mark[data-id="${id}"]`)];
  }

  function unpaint(id) {
    for (const mark of marksOf(id)) {
      mark.replaceWith(...mark.childNodes);
    }
    root.normalize();
  }

  // ---- side list --------------------------------------------------------------

  function renderList() {
    list.textContent = "";
    empty.hidden = highlights.length > 0;
    highlights.slice().sort((a, b) => a.start_offset - b.start_offset).forEach((h) => {
      const li = document.createElement("li");
      const dot = document.createElement("i");
      dot.className = "dot s-" + h.color;
      const link = document.createElement("a");
      link.href = "#hl-" + h.id;
      link.textContent = h.quote.length > 110 ? h.quote.slice(0, 110) + "…" : h.quote;
      link.addEventListener("click", (e) => { e.preventDefault(); flash(h.id); });
      li.append(dot, link);
      list.append(li);
    });
  }

  function flash(id) {
    const marks = marksOf(id);
    if (!marks.length) return;
    marks[0].scrollIntoView({ behavior: "smooth", block: "center" });
    marks.forEach((m) => {
      m.classList.remove("flash-mark");
      void m.offsetWidth;
      m.classList.add("flash-mark");
    });
  }

  // ---- toolbar ------------------------------------------------------------------

  function placeToolbar(rect) {
    toolbar.hidden = false;
    if (matchMedia("(pointer: coarse)").matches || innerWidth < 640) {
      toolbar.classList.add("is-docked");
      toolbar.style.left = toolbar.style.top = "";
      return;
    }
    toolbar.classList.remove("is-docked");
    const w = toolbar.offsetWidth;
    const h = toolbar.offsetHeight;
    const left = Math.min(Math.max(8, rect.left + rect.width / 2 - w / 2), innerWidth - w - 8);
    const top = rect.top > h + 16 ? rect.top - h - 8 : rect.bottom + 8;
    toolbar.style.left = left + "px";
    toolbar.style.top = top + "px";
  }

  function hideToolbar() {
    toolbar.hidden = true;
    pending = null;
    activeId = null;
  }

  function showLookup(text) {
    const key = text.trim().toLowerCase().replace(/[.,;:!?'’"“”()]+$/, "");
    const translation = glossary.get(key) || glossary.get(key.replace(/s$/, ""));
    lookup.hidden = !translation;
    lookup.textContent = translation || "";
  }

  function currentSelection() {
    const sel = getSelection();
    if (!sel.rangeCount || sel.isCollapsed) return null;
    const range = sel.getRangeAt(0).cloneRange();
    if (!range.intersectsNode(root)) return null;
    // Clamp a selection that spills outside the article.
    if (!root.contains(range.startContainer)) range.setStart(root, 0);
    if (!root.contains(range.endContainer)) range.setEnd(root, root.childNodes.length);
    const before = document.createRange();
    before.selectNodeContents(root);
    before.setEnd(range.startContainer, range.startOffset);
    let start = before.toString().length;
    let end = start + range.toString().length;
    const full = root.textContent;
    while (start < end && /\s/.test(full[start])) start++;
    while (end > start && /\s/.test(full[end - 1])) end--;
    if (end <= start) return null;
    return { start, end, text: full.slice(start, end), display: sel.toString(), rect: range.getBoundingClientRect() };
  }

  const onSelection = debounce(() => {
    const current = currentSelection();
    if (!current) {
      if (pending) hideToolbar();
      return;
    }
    pending = current;
    activeId = null;
    delBtn.hidden = true;
    showLookup(current.text);
    placeToolbar(current.rect);
  }, 120);

  document.addEventListener("selectionchange", onSelection);
  // Keep the text selected while pressing toolbar buttons.
  toolbar.addEventListener("mousedown", (e) => e.preventDefault());

  root.addEventListener("click", (e) => {
    if (!getSelection().isCollapsed) return;
    const mark = e.target.closest("mark[data-id]");
    if (!mark) return;
    activeId = Number(mark.dataset.id);
    pending = null;
    delBtn.hidden = false;
    lookup.hidden = true;
    placeToolbar(mark.getBoundingClientRect());
  });

  document.addEventListener("click", (e) => {
    if (activeId !== null && !e.target.closest("#hl-toolbar, mark[data-id]")) hideToolbar();
  });
  window.addEventListener("scroll", () => {
    if (activeId !== null && !toolbar.classList.contains("is-docked")) hideToolbar();
  }, { passive: true });

  // ---- actions ------------------------------------------------------------------

  toolbar.querySelectorAll("[data-color]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const color = btn.dataset.color;
      if (activeId !== null) {
        const id = activeId;
        await api("/highlights/" + id, "PATCH", { color });
        const h = highlights.find((x) => x.id === id);
        h.color = color;
        marksOf(id).forEach((m) => { m.className = "m-" + color; });
        renderList();
        hideToolbar();
      } else if (pending) {
        const sel = pending;
        const { id } = await api("/highlights", "POST", {
          article: data.article, start: sel.start, end: sel.end, quote: sel.text, color,
        });
        const h = { id, start_offset: sel.start, end_offset: sel.end, quote: sel.text, color };
        highlights.push(h);
        paint(h);
        renderList();
        getSelection().removeAllRanges();
        hideToolbar();
      }
    });
  });

  delBtn.addEventListener("click", async () => {
    const id = activeId;
    await api("/highlights/" + id, "DELETE");
    unpaint(id);
    highlights = highlights.filter((h) => h.id !== id);
    renderList();
    hideToolbar();
  });

  document.getElementById("hl-clip").addEventListener("click", async () => {
    const quote = pending ? pending.display : (highlights.find((h) => h.id === activeId) || {}).quote;
    if (!quote) return;
    const target = document.getElementById("note-target").value;
    await api("/notes/clip", "POST", {
      article: data.article, quote, note_id: target ? Number(target) : null,
    });
    getSelection().removeAllRanges();
    hideToolbar();
    toast("Цитата добавлена в конспект.", { href: data.notesUrl, text: "Открыть" });
  });

  const readBtn = document.getElementById("mark-read");
  readBtn.addEventListener("click", async () => {
    await api("/progress", "POST", { kind: "article", results: [{ id: data.article, correct: true }] });
    readBtn.classList.add("is-done");
    readBtn.setAttribute("aria-pressed", "true");
    readBtn.textContent = "Прочитано ✓";
  });

  // ---- start ------------------------------------------------------------------

  highlights = data.highlights.map(resolve).filter(Boolean);
  highlights.forEach(paint);
  renderList();
  const match = location.hash.match(/^#hl-(\d+)$/);
  if (match) setTimeout(() => flash(Number(match[1])), 200);
})();
