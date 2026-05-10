const PUBLICATION_SELECTORS = {
  carousel: "[data-publication-carousel]",
  chart: "[data-publication-year-chart]",
  metaDetails: "[data-publication-meta-details]",
  next: "[data-publication-carousel-next]",
  previous: "[data-publication-carousel-prev]",
  shell: "[data-publication-carousel-shell]",
  slide: "[data-publication-slide]",
  yearButton: "[data-publication-year]",
};

const PUBLICATION_COMPACT_META_WIDTH = 360;

function initPublicationCarousel() {
  const carousel = document.querySelector(PUBLICATION_SELECTORS.carousel);
  const chart = document.querySelector(PUBLICATION_SELECTORS.chart);
  if (!carousel || !chart) {
    return;
  }

  const slides = Array.from(carousel.querySelectorAll(PUBLICATION_SELECTORS.slide));
  const buttons = Array.from(chart.querySelectorAll(PUBLICATION_SELECTORS.yearButton));
  const shell = carousel.closest(PUBLICATION_SELECTORS.shell);
  const previous = document.querySelector(PUBLICATION_SELECTORS.previous);
  const next = document.querySelector(PUBLICATION_SELECTORS.next);
  if (!slides.length || !buttons.length) {
    return;
  }

  const carouselController = PortfolioUI.initItemCarousel({
    scroller: carousel,
    items: slides,
    previous,
    next,
    activeClass: null,
    onUpdate: (activeIndex) => {
      setActivePublicationYear(buttons, slides[activeIndex]?.dataset.publicationSlideYear);
    },
  });

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const year = button.dataset.publicationYear;
      const slide = slides.find((item) => item.dataset.publicationSlideYear === year);
      if (slide) {
        carouselController?.scrollToItem(slide, "smooth");
      }
    });
  });

  window.addEventListener("resize", () => {
    carouselController?.update();
    updatePublicationMetaMode(carousel, slides, shell);
  });

  updatePublicationMetaMode(carousel, slides, shell);
}

function setActivePublicationYear(buttons, year) {
  buttons.forEach((button) => {
    const isActive = button.dataset.publicationYear === year;
    PortfolioUI.setActiveState(button, isActive, "is-active");
  });
}

function updatePublicationMetaMode(carousel, slides, shell) {
  const firstSlide = slides[0];
  if (!firstSlide) {
    return;
  }

  const isCompact = firstSlide.getBoundingClientRect().width < PUBLICATION_COMPACT_META_WIDTH;
  shell?.classList.toggle("is-compact-publications", isCompact);
  PortfolioUI.setDetailsOpen(carousel, PUBLICATION_SELECTORS.metaDetails, !isCompact);
}

initPublicationCarousel();
