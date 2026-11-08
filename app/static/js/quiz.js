"use strict";
(function () {
  const questions = pageData();
  const $ = (id) => document.getElementById(id);
  let index = 0;
  let score = 0;
  const mistakes = [];

  function show() {
    const q = questions[index];
    $("quiz-count").textContent = `Вопрос ${index + 1} из ${questions.length}`;
    $("quiz-bar").style.width = (100 * index) / questions.length + "%";
    $("quiz-question").textContent = q.question;
    $("quiz-feedback").hidden = true;
    $("quiz-next").hidden = true;
    const box = $("quiz-options");
    box.textContent = "";
    shuffled(q.options.map((text, i) => ({ text, i }))).forEach((opt) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "option";
      b.textContent = opt.text;
      b.dataset.i = opt.i;
      b.addEventListener("click", () => answer(q, opt.i));
      box.append(b);
    });
  }

  function answer(q, chosen) {
    const correct = chosen === q.answer;
    if (correct) score++;
    else mistakes.push({ q, chosen });
    document.querySelectorAll(".option").forEach((b) => {
      b.disabled = true;
      const i = Number(b.dataset.i);
      if (i === q.answer) b.classList.add("is-right");
      else if (i === chosen) b.classList.add("is-wrong");
    });
    const fb = $("quiz-feedback");
    fb.textContent = "";
    const head = document.createElement("strong");
    head.textContent = correct ? "Верно. " : "Неверно. ";
    fb.append(head, q.explanation || "");
    fb.className = "feedback " + (correct ? "fb-right" : "fb-wrong");
    fb.hidden = false;
    $("quiz-next").textContent = index + 1 < questions.length ? "Дальше" : "Результат";
    $("quiz-next").hidden = false;
    $("quiz-next").focus();
    api("/progress", "POST", { kind: "quiz", results: [{ id: q.id, correct }] });
  }

  function finish() {
    api("/progress", "POST", { kind: "quiz", results: [], attempt: { score, total: questions.length } });
    $("quiz").hidden = true;
    $("quiz-result").hidden = false;
    $("result-score").textContent = `${score} из ${questions.length}`;
    const box = $("result-mistakes");
    if (!mistakes.length) {
      box.textContent = "Без ошибок.";
      return;
    }
    const title = document.createElement("h2");
    title.textContent = "Разбор ошибок";
    box.append(title);
    mistakes.forEach(({ q }) => {
      const div = document.createElement("div");
      div.className = "mistake";
      const p = document.createElement("p");
      p.textContent = q.question;
      const a = document.createElement("strong");
      a.textContent = q.options[q.answer];
      const e = document.createElement("p");
      e.className = "muted";
      e.textContent = q.explanation || "";
      div.append(p, a, e);
      box.append(div);
    });
  }

  $("quiz-next").addEventListener("click", () => {
    index++;
    if (index < questions.length) show();
    else finish();
  });

  show();
})();
