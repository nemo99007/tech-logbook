(function () {
  var KEY = "techlog-lang", root = document.documentElement, saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  var lang = saved || ((navigator.language || "").toLowerCase().indexOf("ko") === 0 ? "ko" : "en");
  function apply(v) {
    lang = v; root.setAttribute("data-lang", v === "both" ? "" : v);
    try { localStorage.setItem(KEY, v); } catch (e) {}
    document.querySelectorAll(".lang-toggle button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.v === v ? "true" : "false"); });
  }
  document.addEventListener("DOMContentLoaded", function () {
    if (!document.querySelector(".en, .ko")) return;
    var box = document.createElement("div"); box.className = "lang-toggle";
    [["en", "EN"], ["ko", "한국어"], ["both", "EN+한"]].forEach(function (x) {
      var b = document.createElement("button"); b.textContent = x[1]; b.dataset.v = x[0];
      b.onclick = function () { apply(x[0]); }; box.appendChild(b); });
    var bar = document.querySelector(".md-header__inner"), search = bar && bar.querySelector(".md-search");
    if (bar) bar.insertBefore(box, search || null); else document.body.appendChild(box);
    apply(lang);
  });
  root.setAttribute("data-lang", lang === "both" ? "" : lang);
})();
