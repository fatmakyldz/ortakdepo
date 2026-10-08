(function () {
  var saved = null;
  try { saved = localStorage.getItem("tema"); } catch (e) {}
  if (saved === "light" || saved === "dark") document.documentElement.setAttribute("data-theme", saved);
})();
