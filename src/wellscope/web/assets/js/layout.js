// Layout behaviour: drawers on small screens, sidebar tabs, theme and the full-report dialog.
import { describeError, getJSON } from "./api.js";
import { el, icon, readPreference, writePreference } from "./dom.js";

const THEMES = ["system", "light", "dark"];
const THEME_ICONS = { system: "system", light: "sun", dark: "moon" };
const THEME_KEY = "wellscope-theme";
const $ = (id) => document.getElementById(id);

/** Wire layout controls; `onNewChat` runs for the "new conversation" button. */
export function wireLayout({ onNewChat }) {
  applyTheme(readPreference(THEME_KEY, "system"));
  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "toggle-sidebar") toggleDrawer("sidebar");
    if (action === "toggle-sources") toggleDrawer("sources");
    if (action === "cycle-theme") cycleTheme();
    if (action === "new-chat") onNewChat();
    if (action === "close-report") $("report-dialog").close();
  });
  $("backdrop").addEventListener("click", closeDrawers);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawers();
  });
  wireTabs();
}

export function openDrawer(id) {
  closeDrawers();
  $(id).classList.add("is-open");
  $("backdrop").hidden = false;
  for (const button of document.querySelectorAll(`[aria-controls="${id}"]`)) {
    button.setAttribute("aria-expanded", "true");
  }
  $(id).querySelector("button, input, [tabindex]")?.focus();
}

export function closeDrawers() {
  for (const drawer of document.querySelectorAll(".drawer.is-open")) drawer.classList.remove("is-open");
  $("backdrop").hidden = true;
  for (const button of document.querySelectorAll("[aria-controls][aria-expanded]")) {
    button.setAttribute("aria-expanded", "false");
  }
}

function toggleDrawer(id) {
  if ($(id).classList.contains("is-open")) closeDrawers();
  else openDrawer(id);
}

/** Tabs with arrow-key navigation (WAI-ARIA tabs pattern). */
function wireTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const select = (tab) => {
    for (const other of tabs) {
      const selected = other === tab;
      other.setAttribute("aria-selected", String(selected));
      other.tabIndex = selected ? 0 : -1;
      $(other.getAttribute("aria-controls")).hidden = !selected;
    }
    tab.focus();
  };
  for (const tab of tabs) {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (step) select(tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length]);
    });
  }
}

function cycleTheme() {
  const current = readPreference(THEME_KEY, "system");
  const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
  writePreference(THEME_KEY, next);
  applyTheme(next);
}

function applyTheme(theme) {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  const button = document.querySelector('[data-action="cycle-theme"]');
  button.replaceChildren(icon(THEME_ICONS[theme] ?? "system"));
  button.setAttribute("aria-label", `Theme: ${theme}. Change theme`);
  button.title = `Theme: ${theme}`;
}

/** Show a whole report in the dialog. */
export async function openReport(docId) {
  const dialog = $("report-dialog");
  $("report-title").textContent = "Loading report…";
  $("report-meta").textContent = "";
  $("report-body").replaceChildren();
  dialog.showModal();
  try {
    const report = await getJSON(`/api/sources/${encodeURIComponent(docId)}`);
    $("report-title").textContent = report.label;
    $("report-meta").textContent = report.period ? `Covers ${report.period}` : "";
    // Sanitised on the server, like answers.
    $("report-body").innerHTML = report.html;
  } catch (error) {
    $("report-title").textContent = "Report unavailable";
    $("report-body").replaceChildren(el("p", { text: describeError(error) }));
  }
}
