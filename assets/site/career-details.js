const CAREER_DETAIL_SELECTORS = {
  filterButton: "button[data-career-detail-filter]",
  filters: "[data-career-detail-filters]",
  item: "[data-career-detail-items] [data-career-category]",
};

const CAREER_ALL_FILTER = "all";

function initCareerDetailFilters() {
  const filterGroup = document.querySelector(CAREER_DETAIL_SELECTORS.filters);
  const items = Array.from(document.querySelectorAll(CAREER_DETAIL_SELECTORS.item));
  if (!filterGroup || !items.length) {
    return;
  }

  const buttons = PortfolioUI.elements(filterGroup, CAREER_DETAIL_SELECTORS.filterButton);
  const categoryButtons = buttons.filter(
    (button) => button.dataset.careerDetailFilter !== CAREER_ALL_FILTER,
  );

  filterGroup.addEventListener("click", (event) => {
    const button = event.target.closest(CAREER_DETAIL_SELECTORS.filterButton);
    if (!button) {
      return;
    }

    if (button.dataset.careerDetailFilter === CAREER_ALL_FILTER) {
      categoryButtons.forEach((categoryButton) => setCareerFilterActive(categoryButton, true));
    } else {
      setCareerFilterActive(button, !button.classList.contains("active"));
      if (!categoryButtons.some((categoryButton) => categoryButton.classList.contains("active"))) {
        categoryButtons.forEach((categoryButton) => setCareerFilterActive(categoryButton, true));
      }
    }

    updateCareerDetailFilters(buttons, categoryButtons, items);
  });

  updateCareerDetailFilters(buttons, categoryButtons, items);
}

function updateCareerDetailFilters(buttons, categoryButtons, items) {
  const activeCategories = new Set(
    categoryButtons
      .filter((button) => button.classList.contains("active"))
      .map((button) => button.dataset.careerDetailFilter),
  );

  const allButton = buttons.find(
    (button) => button.dataset.careerDetailFilter === CAREER_ALL_FILTER,
  );
  const allSelected = activeCategories.size === categoryButtons.length;
  if (allButton) {
    setCareerFilterActive(allButton, allSelected);
  }

  items.forEach((item) => {
    item.hidden = !activeCategories.has(item.dataset.careerCategory);
  });
}

function setCareerFilterActive(button, isActive) {
  PortfolioUI.setActiveState(button, isActive);
}

document.addEventListener("DOMContentLoaded", initCareerDetailFilters);
