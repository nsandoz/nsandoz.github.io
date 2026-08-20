// Loads shared header/footer markup from partials/ so it only needs to be
// edited in one place. Any element with a `data-include` attribute gets its
// contents replaced with the fetched partial's HTML. Elements additionally
// marked `data-mark-nav` get the current page's nav link flagged `selected`
// once the partial is in place (replaces the old hardcoded `class="selected"`
// that used to be duplicated per page).
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-include]').forEach(function (el) {
    var path = el.getAttribute('data-include');
    fetch(path)
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Failed to load ' + path + ': ' + response.status);
        }
        return response.text();
      })
      .then(function (html) {
        el.innerHTML = html;
        if (el.hasAttribute('data-mark-nav')) {
          markActiveNav(el);
        }
      })
      .catch(function (err) {
        console.error(err);
      });
  });
});

// Reduce a path to a bare page name so the comparison survives the URL forms a
// static host may serve the same page under: "gallery.html", "gallery" (GitHub
// Pages resolves extensionless URLs), "/" and "" (both meaning the home page).
function pageName(path) {
  var last = path.split('/').pop();
  if (!last) {
    return 'index';
  }
  return last.replace(/\.s?html?$/i, '');
}

function markActiveNav(headerEl) {
  var current = pageName(window.location.pathname);
  headerEl.querySelectorAll('nav a').forEach(function (link) {
    var isCurrent = pageName(link.getAttribute('href') || '') === current;
    link.parentElement.classList.toggle('selected', isCurrent);
  });
}
