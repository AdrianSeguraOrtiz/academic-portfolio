const DISSEMINATION_FILTER_SELECTOR = "[data-dissemination-filters]";
const DISSEMINATION_CAROUSEL_SELECTOR = "[data-dissemination-carousel]";
const DISSEMINATION_ITEM_SELECTOR = "[data-dissemination-items] [data-category]";
const DISSEMINATION_BUTTON_SELECTOR = "button[data-filter]";
const DISSEMINATION_ALL_FILTER = "all";
const DISSEMINATION_TRACK_SELECTOR = "[data-dissemination-items]";
const DISSEMINATION_PREV_SELECTOR = "[data-dissemination-prev]";
const DISSEMINATION_NEXT_SELECTOR = "[data-dissemination-next]";
const DISSEMINATION_DETAILS_SELECTOR = "[data-media-details]";

function initDisseminationFilters() {
  const filterGroup = document.querySelector(DISSEMINATION_FILTER_SELECTOR);
  const items = Array.from(document.querySelectorAll(DISSEMINATION_ITEM_SELECTOR));
  const carousel = document.querySelector(DISSEMINATION_CAROUSEL_SELECTOR);
  if (!filterGroup || items.length === 0) {
    return;
  }

  filterGroup.addEventListener("click", (event) => {
    const button = event.target.closest(DISSEMINATION_BUTTON_SELECTOR);
    if (!button) {
      return;
    }

    const activeFilter = button.dataset.filter;
    PortfolioUI.elements(filterGroup, DISSEMINATION_BUTTON_SELECTOR).forEach((filterButton) => {
      const isActive = filterButton === button;
      PortfolioUI.setActiveState(filterButton, isActive);
    });

    items.forEach((item) => {
      item.hidden = activeFilter !== DISSEMINATION_ALL_FILTER && item.dataset.category !== activeFilter;
    });
    resetDisseminationCarousel(carousel);
  });
}

function initDisseminationCarousel() {
  const carousel = document.querySelector(DISSEMINATION_CAROUSEL_SELECTOR);
  if (!carousel) {
    return;
  }

  const track = carousel.querySelector(DISSEMINATION_TRACK_SELECTOR);
  const previousButton = carousel.querySelector(DISSEMINATION_PREV_SELECTOR);
  const nextButton = carousel.querySelector(DISSEMINATION_NEXT_SELECTOR);
  if (!track || !previousButton || !nextButton) {
    return;
  }

  previousButton.addEventListener("click", () => {
    track.scrollBy({ left: -track.clientWidth, behavior: "smooth" });
  });
  nextButton.addEventListener("click", () => {
    track.scrollBy({ left: track.clientWidth, behavior: "smooth" });
  });
  track.addEventListener("scroll", () => updateDisseminationCarouselControls(carousel), {
    passive: true,
  });
  window.addEventListener("resize", () => {
    updateDisseminationCarouselControls(carousel);
  });
  updateDisseminationCarouselControls(carousel);
}

function resetDisseminationCarousel(carousel) {
  if (!carousel) {
    return;
  }

  const track = carousel.querySelector(DISSEMINATION_TRACK_SELECTOR);
  if (!track) {
    return;
  }

  track.scrollTo({ left: 0, behavior: "smooth" });
  window.setTimeout(() => {
    updateDisseminationCarouselControls(carousel);
  }, 180);
}

function updateDisseminationCarouselControls(carousel) {
  const track = carousel.querySelector(DISSEMINATION_TRACK_SELECTOR);
  const previousButton = carousel.querySelector(DISSEMINATION_PREV_SELECTOR);
  const nextButton = carousel.querySelector(DISSEMINATION_NEXT_SELECTOR);
  if (!track || !previousButton || !nextButton) {
    return;
  }

  PortfolioUI.updateScrollControls(track, previousButton, nextButton);
}

function initDisseminationDetails() {
  const carousel = document.querySelector(DISSEMINATION_CAROUSEL_SELECTOR);
  const details = Array.from(document.querySelectorAll(DISSEMINATION_DETAILS_SELECTOR));
  if (!carousel || details.length === 0) {
    return;
  }

  PortfolioUI.setDetailsOpen(carousel, DISSEMINATION_DETAILS_SELECTOR, false);
}

function initDissemination() {
  initDisseminationFilters();
  initDisseminationCarousel();
  initDisseminationDetails();
}

document.addEventListener("DOMContentLoaded", initDissemination);
