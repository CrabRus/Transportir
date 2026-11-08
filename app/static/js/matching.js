"use strict";
(function () {
  const item = pageData();
  const $ = (id) => document.getElementById(id);
  const total = item.pairs.length;
  let selected = null;
  let matched = 0;
  let errors = 0;

  function makeButton(text, index, side) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "match-item";
    b.textContent = text;
    b.dataset.i = index;
    b.addEventListener("click", () => pick(b, side));
    return b;
  }

  function pick(button, side) {
    if (button.disabled) return;
    if (!selected || selected.side === side) {
      if (selected) selected.button.classList.remove("is-selected");
      selected = selected && selected.button === button ? null : { button, side };
      if (selected) button.classList.add("is-selected");
      return;
    }
    const other = selected.button;
    other.classList.remove("is-selected");
    selected = null;
    if (other.dataset.i === button.dataset.i) {
      [other, button].forEach((b) => { b.disabled = true; b.classList.add("is-matched"); });
      matched++;
      update();
    } else {
      errors++;
      [other, button].forEach((b) => {
        b.classList.remove("is-miss");
        void b.offsetWidth;
        b.classList.add("is-miss");
      });
      update();
    }
  }

  function update() {
    $("match-count").textContent = `${matched} из ${total} · ошибок: ${errors}`;
    if (matched === total) {
      $("match-done").hidden = false;
      $("match-result").textContent = errors ? `Готово, ошибок: ${errors}` : "Без единой ошибки";
      api("/progress", "POST", { kind: "matching", results: [{ id: item.id, correct: errors === 0 }] });
    }
  }

  const left = item.pairs.map((p, i) => ({ text: p[0], i }));
  const right = item.pairs.map((p, i) => ({ text: p[1], i }));
  shuffled(left).forEach((x) => $("match-left").append(makeButton(x.text, x.i, "left")));
  shuffled(right).forEach((x) => $("match-right").append(makeButton(x.text, x.i, "right")));
  update();
})();
