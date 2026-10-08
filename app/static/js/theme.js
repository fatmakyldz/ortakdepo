// Tema: sayfa çizilmeden önce çalışır ki açık/koyu arasında göz kırpma olmasın.
// Seçim yoksa cihazın ayarı geçerlidir.
(function () {
  var saved = null;
  try { saved = localStorage.getItem("tema"); } catch (e) { /* gizli sekme vb. */ }
  if (saved === "acik" || saved === "koyu") {
    document.documentElement.setAttribute("data-theme", saved === "koyu" ? "dark" : "light");
  }
})();
