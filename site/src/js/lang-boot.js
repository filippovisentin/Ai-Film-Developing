// Caricato nel <head> prima del resto: sceglie lingua e variante grafica subito, senza sfarfallio.
(function () {
  var root = document.documentElement, saved = null, tema = null;
  try { saved = localStorage.getItem("afd-lang"); tema = localStorage.getItem("afd-tema"); } catch (e) {}
  var l = saved || ((navigator.language || "it").slice(0, 2) === "it" ? "it" : "en");
  root.dataset.lang = l === "en" ? "en" : "it";
  root.lang = root.dataset.lang;
  var asked = /[?&]tema=(oscura|archivio)\b/.exec(location.search);
  if (asked) tema = asked[1];
  root.dataset.tema = tema === "archivio" ? "archivio" : "oscura";
})();
