// Sets the theme before the page paints, so nothing flashes: the saved choice, else the operating system's, else light.
// A separate file, not inline, because the server's content security policy allows scripts from this site only.
(function () {
  var t = null;
  try { t = localStorage.getItem("enough-theme"); } catch (e) {}
  if (t !== "dark" && t !== "light") t = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", t);
  if (t === "dark") { var m = document.querySelector('meta[name="theme-color"]'); if (m) m.setAttribute("content", "#090914"); }
})();
