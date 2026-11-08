"use strict";
(function () {
  const data = pageData();
  const $ = (id) => document.getElementById(id);
  const answer = $("answer");
  const boxes = [...document.querySelectorAll(".checks input")];

  const checked = () => boxes.filter((b) => b.checked).map((b) => Number(b.dataset.i));

  function save(final) {
    return api("/open/" + encodeURIComponent(data.id), "POST", {
      answer: answer.value, checked: checked(), final: Boolean(final),
    }).then(() => { $("save-state").textContent = "Сохранено"; });
  }

  const autosave = debounce(() => save(false), 800);
  answer.addEventListener("input", () => {
    $("save-state").textContent = "Сохранение…";
    autosave();
  });

  function updateScore() {
    $("check-score").textContent = `Отмечено ${checked().length} из ${data.total}`;
  }
  boxes.forEach((b) => b.addEventListener("change", () => { updateScore(); save(false); }));

  function reveal() {
    $("review").hidden = false;
    $("reveal").hidden = true;
    updateScore();
  }

  $("reveal").addEventListener("click", () => {
    reveal();
    save(false);
    $("review").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  $("finish").addEventListener("click", async () => {
    await save(true);
    location.href = data.listUrl;
  });

  if (data.reviewed) reveal();
})();
