const DISSEMINATION_FILTER_SELECTOR = "[data-dissemination-filters]";
const DISSEMINATION_ITEM_SELECTOR = "[data-dissemination-items] [data-category]";
const DISSEMINATION_BUTTON_SELECTOR = "button[data-filter]";
const DISSEMINATION_ALL_FILTER = "all";

function initDisseminationFilters() {
  const filterGroup = document.querySelector(DISSEMINATION_FILTER_SELECTOR);
  const items = Array.from(document.querySelectorAll(DISSEMINATION_ITEM_SELECTOR));
  if (!filterGroup || items.length === 0) {
    return;
  }

  filterGroup.addEventListener("click", (event) => {
    const button = event.target.closest(DISSEMINATION_BUTTON_SELECTOR);
    if (!button) {
      return;
    }

    const activeFilter = button.dataset.filter;
    filterGroup.querySelectorAll(DISSEMINATION_BUTTON_SELECTOR).forEach((filterButton) => {
      const isActive = filterButton === button;
      filterButton.classList.toggle("active", isActive);
      filterButton.setAttribute("aria-pressed", String(isActive));
    });

    items.forEach((item) => {
      item.hidden = activeFilter !== DISSEMINATION_ALL_FILTER && item.dataset.category !== activeFilter;
    });
  });
}

document.addEventListener("DOMContentLoaded", initDisseminationFilters);
