const PortfolioUI = (() => {
  function elements(root, selector) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function maxScrollLeft(scroller) {
    return Math.max(scroller.scrollWidth - scroller.clientWidth, 0);
  }

  function scrollToEnd(scroller, behavior = "auto") {
    scroller.scrollTo({
      left: maxScrollLeft(scroller),
      behavior,
    });
  }

  function itemOffsetLeft(scroller, item) {
    return (
      item.getBoundingClientRect().left
      - scroller.getBoundingClientRect().left
      + scroller.scrollLeft
    );
  }

  function activeItemIndex(scroller, items) {
    const viewportStart = scroller.scrollLeft;
    const visibleItems = items
      .map((item, index) => ({
        index,
        offset: itemOffsetLeft(scroller, item),
        width: item.offsetWidth,
      }))
      .filter((item) => item.offset + item.width > viewportStart + 6);

    if (!visibleItems.length) {
      return Math.max(items.length - 1, 0);
    }

    return visibleItems.reduce((closest, item) => (
      Math.abs(item.offset - viewportStart) < Math.abs(closest.offset - viewportStart)
        ? item
        : closest
    )).index;
  }

  function scrollToItem(scroller, item, behavior = "smooth") {
    scroller.scrollTo({
      left: Math.min(itemOffsetLeft(scroller, item), maxScrollLeft(scroller)),
      behavior,
    });
  }

  function scrollToItemIndex(scroller, items, index, behavior = "smooth") {
    if (!items.length) {
      return;
    }

    const boundedIndex = Math.max(0, Math.min(index, items.length - 1));
    scrollToItem(scroller, items[boundedIndex], behavior);
  }

  function updateCarouselControls(scroller, items, previous, next, activeClass) {
    updateScrollControls(scroller, previous, next);

    if (activeClass) {
      const activeIndex = activeItemIndex(scroller, items);
      items.forEach((item, index) => {
        item.classList.toggle(activeClass, index === activeIndex);
      });
    }
  }

  function updateScrollControls(scroller, previous, next) {
    const canScroll = scroller.scrollWidth > scroller.clientWidth + 1;
    if (previous) {
      previous.disabled = !canScroll || scroller.scrollLeft <= 1;
    }
    if (next) {
      next.disabled = !canScroll || scroller.scrollLeft >= maxScrollLeft(scroller) - 1;
    }
  }

  function initItemCarousel({
    scroller,
    items,
    previous,
    next,
    activeClass = "is-active-carousel-item",
    onUpdate = null,
  }) {
    if (!scroller || !items.length) {
      return null;
    }

    const update = () => {
      updateCarouselControls(scroller, items, previous, next, activeClass);
      if (onUpdate) {
        onUpdate(activeItemIndex(scroller, items));
      }
    };

    previous?.addEventListener("click", () => {
      scrollToItemIndex(scroller, items, activeItemIndex(scroller, items) - 1);
    });
    next?.addEventListener("click", () => {
      scrollToItemIndex(scroller, items, activeItemIndex(scroller, items) + 1);
    });
    scroller.addEventListener("scroll", () => window.requestAnimationFrame(update), {
      passive: true,
    });
    window.addEventListener("resize", () => window.requestAnimationFrame(update));
    update();

    return {
      update,
      scrollToIndex: (index, behavior = "smooth") => {
        scrollToItemIndex(scroller, items, index, behavior);
      },
      scrollToItem: (item, behavior = "smooth") => {
        scrollToItem(scroller, item, behavior);
      },
    };
  }

  function setActiveState(element, isActive, className = "active", ariaAttribute = "aria-pressed") {
    element.classList.toggle(className, isActive);
    element.setAttribute(ariaAttribute, String(isActive));
  }

  function setDetailsOpen(root, selector, isOpen) {
    elements(root, selector).forEach((details) => {
      if (isOpen) {
        details.setAttribute("open", "");
      } else {
        details.removeAttribute("open");
      }
    });
  }

  function initExclusiveTabs({
    root,
    tabSelector,
    panelSelector,
    tabDatasetKey,
    panelDatasetKey,
  }) {
    if (!root) {
      return;
    }

    const tabs = elements(root, tabSelector);
    const panels = elements(root, panelSelector);
    if (!tabs.length || !panels.length) {
      return;
    }

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const activeId = tab.dataset[tabDatasetKey];
        tabs.forEach((candidate) => {
          setActiveState(
            candidate,
            candidate.dataset[tabDatasetKey] === activeId,
            "active",
            "aria-selected",
          );
        });
        panels.forEach((panel) => {
          const isActive = panel.dataset[panelDatasetKey] === activeId;
          panel.classList.toggle("active", isActive);
          panel.hidden = !isActive;
        });
      });
    });
  }

  return {
    activeItemIndex,
    elements,
    initExclusiveTabs,
    initItemCarousel,
    maxScrollLeft,
    scrollToEnd,
    scrollToItem,
    scrollToItemIndex,
    setActiveState,
    setDetailsOpen,
    updateScrollControls,
  };
})();
