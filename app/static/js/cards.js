"use strict";
(function () {
  const { cards, kind } = pageData();
  const $ = (id) => document.getElementById(id);
  const total = cards.length;
  let queue = cards.slice();
  let known = 0;
  let flipped = false;
  let reversed = false;

  function view(card) {
    if (kind === "definition") {
      return {
        front: { main: card.term, label: "Термин" },
        back: { main: card.definition, label: "Определение", source: card.source },
      };
    }
    const en = { main: card.term, label: "English", sub: flipped ? card.meaning_en : "" };
    const ru = { main: card.translation, label: "Русский", sub: flipped ? card.meaning_ru : "" };
    return reversed ? { front: ru, back: en } : { front: en, back: ru };
  }

  function render() {
    const card = queue[0];
    $("cards-count").textContent = `Выучено ${known} из ${total}`;
    $("cards-bar").style.width = (100 * known) / total + "%";
    const side = view(card)[flipped ? "back" : "front"];
    $("card-face").textContent = side.label;
    $("card-main").textContent = side.main;
    $("card-sub").textContent = side.sub || "";
    $("card-source").textContent = side.source ? "Источник: " + side.source : "";
    $("card").classList.toggle("is-back", flipped);
    $("card").classList.toggle("is-long", side.main.length > 90);
    $("card-grade").hidden = !flipped;
    $("card-hint").hidden = flipped;
  }

  function grade(correct) {
    if (!flipped) return;
    const card = queue.shift();
    api("/progress", "POST", { kind, results: [{ id: card.id, correct }] });
    if (correct) known++;
    else queue.push(card);
    flipped = false;
    if (queue.length) render();
    else {
      $("cards").hidden = true;
      $("cards-done").hidden = false;
      $("done-text").textContent = `Вы прошли все карточки: ${total}`;
    }
  }

  function flip() {
    flipped = !flipped;
    render();
  }

  $("card").addEventListener("click", flip);
  $("grade-know").addEventListener("click", () => grade(true));
  $("grade-again").addEventListener("click", () => grade(false));
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "BUTTON" && e.code === "Space" && e.target.id !== "card") return;
    if (e.code === "Space") { e.preventDefault(); flip(); }
    else if (e.key === "1") grade(false);
    else if (e.key === "2") grade(true);
  });

  if ($("dir-en")) {
    const setDir = (rev) => {
      reversed = rev;
      flipped = false;
      $("dir-en").setAttribute("aria-pressed", String(!rev));
      $("dir-ru").setAttribute("aria-pressed", String(rev));
      render();
    };
    $("dir-en").addEventListener("click", () => setDir(false));
    $("dir-ru").addEventListener("click", () => setDir(true));
  }

  render();
})();
