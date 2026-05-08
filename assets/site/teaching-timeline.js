const TEACHING_TIMELINE_QUERY = "(max-width: 760px)";
const TEACHING_TIMELINE_SELECTOR = ".teaching-timeline-scroll";
const TEACHING_TIMELINE_FRAME_SELECTOR = ".teaching-timeline-frame";
const TEACHING_TIMELINE_STAGE_SELECTOR = ".teaching-timeline-stage";

function initTeachingTimelineFit() {
  const timelines = Array.from(document.querySelectorAll(TEACHING_TIMELINE_SELECTOR));
  if (!timelines.length) {
    return;
  }

  const updateTimelines = () => {
    timelines.forEach(fitTeachingTimeline);
  };

  updateTimelines();
  window.addEventListener("resize", updateTimelines);
}

function fitTeachingTimeline(scroller) {
  const frame = scroller.querySelector(TEACHING_TIMELINE_FRAME_SELECTOR);
  const stage = scroller.querySelector(TEACHING_TIMELINE_STAGE_SELECTOR);
  if (!frame || !stage) {
    return;
  }

  const stageWidth = cssPixelValue(stage, "--stage-width") || stage.scrollWidth;
  const stageHeight = cssPixelValue(stage, "--timeline-height") || stage.scrollHeight;
  const shouldFit = window.matchMedia?.(TEACHING_TIMELINE_QUERY).matches ?? false;
  const availableWidth = Math.max(scroller.clientWidth, 1);
  const scale = shouldFit ? Math.min(1, availableWidth / stageWidth) : 1;

  scroller.classList.toggle("is-fit-width", scale < 1);
  frame.style.width = scale < 1 ? `${availableWidth}px` : "";
  frame.style.height = scale < 1 ? `${Math.ceil(stageHeight * scale)}px` : "";
  stage.style.width = `${stageWidth}px`;
  stage.style.minHeight = `${stageHeight}px`;
  stage.style.transform = scale < 1 ? `scale(${scale})` : "";
}

function cssPixelValue(element, propertyName) {
  const rawValue = getComputedStyle(element).getPropertyValue(propertyName);
  const numericValue = Number.parseFloat(rawValue);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

initTeachingTimelineFit();
