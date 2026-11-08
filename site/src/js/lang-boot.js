// Caricato nel <head> prima del resto: sceglie la lingua subito, senza mostrare entrambe.
(function () {
  var saved = null;
  try { saved = localStorage.getItem("afd-lang"); } catch (e) {}
  var l = saved || ((navigator.language || "it").slice(0, 2) === "it" ? "it" : "en");
  document.documentElement.dataset.lang = l === "en" ? "en" : "it";
  document.documentElement.lang = document.documentElement.dataset.lang;
})();
