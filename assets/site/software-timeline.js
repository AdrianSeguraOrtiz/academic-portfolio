const SOFTWARE_TIMELINE_SELECTOR = ".software-timeline-scroll";
const SOFTWARE_CAROUSEL_SELECTORS = {
  carousel: "[data-software-carousel]",
  item: "[data-software-carousel-item]",
  layout: ".software-layout",
  next: "[data-software-carousel-next]",
  previous: "[data-software-carousel-prev]",
  snapshot: ".software-snapshot",
  track: "[data-software-carousel-track]",
};

function initSoftwareTimelineScroll() {
  const timelines = Array.from(document.querySelectorAll(SOFTWARE_TIMELINE_SELECTOR));
  if (!timelines.length) {
    return;
  }

  const scrollToLatest = () => {
    timelines.forEach((timeline) => {
      PortfolioUI.scrollToEnd(timeline);
    });
  };

  window.requestAnimationFrame(() => {
    scrollToLatest();
    window.requestAnimationFrame(scrollToLatest);
  });
  window.setTimeout(scrollToLatest, 150);
  window.addEventListener("load", scrollToLatest, { once: true });
  window.addEventListener("resize", () => window.requestAnimationFrame(scrollToLatest));
}

function initSoftwareLayoutSizing() {
  const layout = document.querySelector(SOFTWARE_CAROUSEL_SELECTORS.layout);
  const snapshot = document.querySelector(SOFTWARE_CAROUSEL_SELECTORS.snapshot);
  if (!layout || !snapshot) {
    return;
  }

  const updateLayout = () => {
    const layoutRect = layout.getBoundingClientRect();
    const snapshotRect = snapshot.getBoundingClientRect();
    const isSideBySide = snapshotRect.right < layoutRect.right - 1;
    layout.classList.toggle("is-side-by-side", isSideBySide);
    if (isSideBySide) {
      layout.style.setProperty("--software-snapshot-height", `${snapshotRect.height}px`);
    } else {
      layout.style.removeProperty("--software-snapshot-height");
    }
  };

  window.requestAnimationFrame(updateLayout);
  window.addEventListener("load", updateLayout, { once: true });
  window.addEventListener("resize", () => window.requestAnimationFrame(updateLayout));
}

function initSoftwareCarousels() {
  const carousels = Array.from(document.querySelectorAll(SOFTWARE_CAROUSEL_SELECTORS.carousel));
  carousels.forEach((carousel) => {
    const track = carousel.querySelector(SOFTWARE_CAROUSEL_SELECTORS.track);
    const items = Array.from(carousel.querySelectorAll(SOFTWARE_CAROUSEL_SELECTORS.item));
    const previous = carousel.querySelector(SOFTWARE_CAROUSEL_SELECTORS.previous);
    const next = carousel.querySelector(SOFTWARE_CAROUSEL_SELECTORS.next);
    if (!track || !items.length) {
      return;
    }

    PortfolioUI.initItemCarousel({
      scroller: track,
      items,
      previous,
      next,
    });
  });
}

initSoftwareTimelineScroll();
initSoftwareLayoutSizing();
initSoftwareCarousels();
