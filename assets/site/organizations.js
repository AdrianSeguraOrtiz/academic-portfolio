const ORGANIZATION_TABS_SELECTOR = "[data-organization-tabs]";
const ORGANIZATION_TAB_SELECTOR = "[data-organization-tab]";
const ORGANIZATION_PANEL_SELECTOR = "[data-organization-panel]";

function initOrganizationTabs() {
  const root = document.querySelector(ORGANIZATION_TABS_SELECTOR);
  PortfolioUI.initExclusiveTabs({
    root,
    tabSelector: ORGANIZATION_TAB_SELECTOR,
    panelSelector: ORGANIZATION_PANEL_SELECTOR,
    tabDatasetKey: "organizationTab",
    panelDatasetKey: "organizationPanel",
  });
}

document.addEventListener("DOMContentLoaded", initOrganizationTabs);
