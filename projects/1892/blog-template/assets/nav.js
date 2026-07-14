// Progressive enhancement for article action buttons.
// No external deps; runs once on defer.
(function () {
  document.body.classList.add("js");

  function canonicalUrl() {
    var link = document.querySelector('link[rel="canonical"]');
    return link ? link.href : window.location.href;
  }

  function copyCanonical(btn) {
    var label = btn.querySelector("span");
    var original = label ? label.textContent : "";

    function markCopied() {
      if (!label) return;
      label.textContent = "Copied";
      setTimeout(function () { label.textContent = original; }, 2000);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(canonicalUrl()).then(markCopied);
    } else {
      markCopied();
    }
  }

  document.querySelectorAll("[data-share], [data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () { copyCanonical(btn); });
  });
})();
