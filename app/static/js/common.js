"use strict";

const CSRF = document.querySelector('meta[name="csrf-token"]').content;

async function api(path, method, body) {
  const response = await fetch(window.API_ROOT + path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": CSRF },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 401) {
    location.href = "/login?next=" + encodeURIComponent(location.pathname);
    throw new Error("login required");
  }
  if (!response.ok) {
    toast("Не удалось сохранить. Проверьте соединение.");
    throw new Error("HTTP " + response.status);
  }
  return response.json();
}

function pageData() {
  return JSON.parse(document.getElementById("page-data").textContent);
}

function shuffled(items) {
  const a = items.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

let toastTimer;
function toast(text, link) {
  const el = document.getElementById("toast");
  el.textContent = text;
  if (link) {
    const a = document.createElement("a");
    a.href = link.href;
    a.textContent = link.text;
    el.append(" ", a);
  }
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
