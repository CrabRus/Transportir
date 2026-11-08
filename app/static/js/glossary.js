"use strict";
(function () {
  const search = document.getElementById("gl-search");
  const topic = document.getElementById("gl-topic");
  const entries = [...document.querySelectorAll(".entry")];
  const count = document.getElementById("gl-count");
  const empty = document.getElementById("gl-empty");

  function apply() {
    const q = search.value.trim().toLowerCase();
    const t = topic.value;
    let shown = 0;
    entries.forEach((e) => {
      const ok = (!q || e.dataset.search.includes(q)) && (!t || e.dataset.topic === t);
      e.hidden = !ok;
      if (ok) shown++;
    });
    count.textContent = `Терминов: ${shown}`;
    empty.hidden = shown > 0;
  }

  search.addEventListener("input", apply);
  topic.addEventListener("change", apply);
  apply();
})();
