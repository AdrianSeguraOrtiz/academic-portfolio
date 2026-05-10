const PROJECT_SELECTORS = {
  carousel: "[data-project-carousel]",
  item: "[data-project-carousel-item]",
  metaDetails: "[data-project-meta-details]",
  next: "[data-project-carousel-next]",
  previous: "[data-project-carousel-prev]",
  track: "[data-project-carousel-track]",
};

const PROJECT_COMPACT_META_WIDTH = 360;

function initProjectCarousel() {
  const carousel = document.querySelector(PROJECT_SELECTORS.carousel);
  if (!carousel) {
    return;
  }

  const track = carousel.querySelector(PROJECT_SELECTORS.track);
  const items = Array.from(carousel.querySelectorAll(PROJECT_SELECTORS.item));
  const previous = carousel.querySelector(PROJECT_SELECTORS.previous);
  const next = carousel.querySelector(PROJECT_SELECTORS.next);
  if (!track || !items.length) {
    return;
  }

  PortfolioUI.initItemCarousel({
    scroller: track,
    items,
    previous,
    next,
    onUpdate: () => updateProjectMetaMode(carousel, track, items),
  });
}

function updateProjectMetaMode(carousel, track, items) {
  const firstItem = items[0];
  if (!firstItem) {
    return;
  }

  const isCompact = firstItem.getBoundingClientRect().width < PROJECT_COMPACT_META_WIDTH;
  carousel.classList.toggle("is-compact-projects", isCompact);
  PortfolioUI.setDetailsOpen(track, PROJECT_SELECTORS.metaDetails, !isCompact);
}

document.addEventListener("DOMContentLoaded", initProjectCarousel);
