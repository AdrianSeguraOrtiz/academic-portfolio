const TEACHING_TIMELINE_SELECTOR = ".teaching-timeline-scroll";
const TEACHING_TIMELINE_FRAME_SELECTOR = ".teaching-timeline-frame";
const TEACHING_TIMELINE_STAGE_SELECTOR = ".teaching-timeline-stage";
const TEACHING_ZOOM_IN_SELECTOR = "[data-teaching-zoom-in]";
const TEACHING_ZOOM_OUT_SELECTOR = "[data-teaching-zoom-out]";
const TEACHING_ZOOM_RESET_SELECTOR = "[data-teaching-zoom-reset]";
const TEACHING_ZOOM_STEP = 1.2;
const TEACHING_MAX_USER_SCALE = 2.2;
const teachingTimelineScales = new WeakMap();

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
  bindTeachingZoomControls(updateTimelines);
}

function fitTeachingTimeline(scroller) {
  const frame = scroller.querySelector(TEACHING_TIMELINE_FRAME_SELECTOR);
  const stage = scroller.querySelector(TEACHING_TIMELINE_STAGE_SELECTOR);
  if (!frame || !stage) {
    return;
  }

  const stageWidth = cssPixelValue(stage, "--stage-width") || stage.scrollWidth;
  const stageHeight = cssPixelValue(stage, "--timeline-height") || stage.scrollHeight;
  const availableWidth = Math.max(scroller.clientWidth, 1);
  const fitScale = Math.min(1, availableWidth / stageWidth);
  const userScale = teachingTimelineScales.get(scroller) || 1;
  const scale = fitScale * userScale;

  scroller.classList.toggle("is-fit-width", scale < 1);
  scroller.classList.toggle("is-zoomed", scale > fitScale + 0.01);
  frame.style.width = scale < 1 ? `${availableWidth}px` : `${Math.ceil(stageWidth * scale)}px`;
  frame.style.height = `${Math.ceil(stageHeight * scale)}px`;
  stage.style.width = `${stageWidth}px`;
  stage.style.minHeight = `${stageHeight}px`;
  stage.style.transform = scale === 1 ? "" : `scale(${scale})`;
}

function bindTeachingZoomControls(updateTimelines) {
  const zoomIn = document.querySelector(TEACHING_ZOOM_IN_SELECTOR);
  const zoomOut = document.querySelector(TEACHING_ZOOM_OUT_SELECTOR);
  const zoomReset = document.querySelector(TEACHING_ZOOM_RESET_SELECTOR);

  zoomIn?.addEventListener("click", () => {
    updateTeachingScale(TEACHING_ZOOM_STEP);
    updateTimelines();
  });
  zoomOut?.addEventListener("click", () => {
    updateTeachingScale(1 / TEACHING_ZOOM_STEP);
    updateTimelines();
  });
  zoomReset?.addEventListener("click", () => {
    Array.from(document.querySelectorAll(TEACHING_TIMELINE_SELECTOR)).forEach((scroller) => {
      teachingTimelineScales.set(scroller, 1);
    });
    updateTimelines();
  });
}

function updateTeachingScale(factor) {
  Array.from(document.querySelectorAll(TEACHING_TIMELINE_SELECTOR)).forEach((scroller) => {
    const currentScale = teachingTimelineScales.get(scroller) || 1;
    teachingTimelineScales.set(
      scroller,
      Math.min(Math.max(currentScale * factor, 1), TEACHING_MAX_USER_SCALE),
    );
  });
}

function cssPixelValue(element, propertyName) {
  const rawValue = getComputedStyle(element).getPropertyValue(propertyName);
  const numericValue = Number.parseFloat(rawValue);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

initTeachingTimelineFit();
