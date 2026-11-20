/* Cars page: live search, make filter, rows per page + pagination.
   Plain JavaScript, no page reload. The search matches make, model,
   year and price. The make filter and the search work together,
   then the filtered cars are split into pages. */
(function () {
  var searchInput = document.getElementById("car-search");
  var makeSelect = document.getElementById("car-make");
  var rowsSelect = document.getElementById("car-rows");
  var grid = document.getElementById("car-grid");
  var countText = document.getElementById("car-count");
  var pagesBox = document.getElementById("car-pages");
  var noMatch = document.getElementById("car-no-match");
  if (!grid) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll(".car-card"));
  var page = 1;

  function filteredCards() {
    var q = (searchInput.value || "").trim().toLowerCase();
    var make = makeSelect.value;
    return cards.filter(function (card) {
      if (make && card.getAttribute("data-make") !== make) return false;
      if (q && card.getAttribute("data-search").indexOf(q) === -1) return false;
      return true;
    });
  }

  function perPage() {
    if (rowsSelect.value === "all") return cards.length || 1;
    return parseInt(rowsSelect.value, 10) || 24;
  }

  function renderPages(total, pages) {
    pagesBox.innerHTML = "";
    if (total === 0 || pages <= 1) return;

    function btn(label, target, disabled, active) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.className = "page-btn" + (active ? " active" : "");
      b.disabled = !!disabled;
      b.addEventListener("click", function () {
        page = target;
        render();
        grid.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      pagesBox.appendChild(b);
    }

    btn("‹ Prev", page - 1, page <= 1);
    // Page numbers: show all when few, otherwise a small window.
    var start = 1, end = pages;
    if (pages > 7) {
      start = Math.max(1, Math.min(page - 3, pages - 6));
      end = Math.min(pages, start + 6);
    }
    for (var p = start; p <= end; p++) {
      btn(String(p), p, false, p === page);
    }
    btn("Next ›", page + 1, page >= pages);
  }

  function render() {
    var list = filteredCards();
    var total = list.length;
    var size = perPage();
    var pages = Math.max(1, Math.ceil(total / size));
    if (page > pages) page = pages;
    if (page < 1) page = 1;

    cards.forEach(function (card) { card.style.display = "none"; });
    var from = (page - 1) * size;
    var to = Math.min(total, from + size);
    for (var i = from; i < to; i++) {
      list[i].style.display = "";
    }

    if (total === 0) {
      countText.textContent = "0 cars found.";
      noMatch.hidden = false;
    } else if (rowsSelect.value === "all") {
      countText.textContent = total + " cars found — showing all.";
      noMatch.hidden = true;
    } else {
      countText.textContent = total + " cars found — showing " +
        (from + 1) + "–" + to + ".";
      noMatch.hidden = true;
    }
    renderPages(total, pages);
  }

  searchInput.addEventListener("input", function () { page = 1; render(); });
  makeSelect.addEventListener("change", function () { page = 1; render(); });
  rowsSelect.addEventListener("change", function () { page = 1; render(); });

  render();
})();
