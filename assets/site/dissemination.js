function initDisseminationFilters() {
  const filterGroup = document.querySelector("[data-dissemination-filters]");
  const items = Array.from(document.querySelectorAll("[data-dissemination-items] [data-category]"));
  if (!filterGroup || items.length === 0) {
    return;
  }

  filterGroup.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-filter]");
    if (!button) {
      return;
    }

    const activeFilter = button.dataset.filter;
    filterGroup.querySelectorAll("button[data-filter]").forEach((filterButton) => {
      const isActive = filterButton === button;
      filterButton.classList.toggle("active", isActive);
      filterButton.setAttribute("aria-pressed", String(isActive));
    });

    items.forEach((item) => {
      item.hidden = activeFilter !== "all" && item.dataset.category !== activeFilter;
    });
  });
}

document.addEventListener("DOMContentLoaded", initDisseminationFilters);
