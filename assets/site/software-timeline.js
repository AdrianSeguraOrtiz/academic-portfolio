const SOFTWARE_TIMELINE_SELECTOR = ".software-timeline-scroll";

function initSoftwareTimelineScroll() {
  const timelines = Array.from(document.querySelectorAll(SOFTWARE_TIMELINE_SELECTOR));
  if (!timelines.length) {
    return;
  }

  const scrollToLatest = () => {
    timelines.forEach((timeline) => {
      timeline.scrollTo({
        left: Math.max(timeline.scrollWidth - timeline.clientWidth, 0),
        behavior: "auto",
      });
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

initSoftwareTimelineScroll();
