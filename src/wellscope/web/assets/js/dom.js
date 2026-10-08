// DOM helpers. Untrusted text always goes through textContent; the only HTML inserted is
// answer and report markup that the server has already sanitised.

const SVG_NS = "http://www.w3.org/2000/svg";

const ICONS = {
  menu: ["M4 6h16", "M4 12h16", "M4 18h16"],
  plus: ["M12 5v14", "M5 12h14"],
  system: ["M3 4h18v12H3z", "M8 20h8", "M12 16v4"],
  sun: [
    "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8",
    "M12 2v2", "M12 20v2", "M4.9 4.9l1.4 1.4", "M17.7 17.7l1.4 1.4",
    "M2 12h2", "M20 12h2", "M4.9 19.1l1.4-1.4", "M17.7 6.3l1.4-1.4",
  ],
  moon: ["M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"],
  book: [
    "M4 19.5A2.5 2.5 0 0 1 6.5 17H20",
    "M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z",
  ],
  close: ["M18 6 6 18", "M6 6l12 12"],
  check: ["M20 6 9 17l-5-5"],
  info: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18", "M12 16v-4", "M12 8h.01"],
  alert: [
    "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
    "M12 9v4",
    "M12 17h.01",
  ],
  ban: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18", "M5.6 5.6l12.8 12.8"],
  send: ["M22 2 11 13", "M22 2 15 22l-4-9-9-4z"],
  stop: ["M7 7h10v10H7z"],
  copy: ["M9 9h11v11H9z", "M5 15H4V4h11v1"],
  external: ["M14 3h7v7", "M10 14 21 3", "M21 14v7H3V3h7"],
};

/** An SVG icon; decorative, so hidden from assistive technology. */
export function icon(name) {
  const svg = document.createElementNS(SVG_NS, "svg");
  for (const [attribute, value] of Object.entries({
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "aria-hidden": "true",
    focusable: "false",
  })) {
    svg.setAttribute(attribute, value);
  }
  for (const d of ICONS[name] ?? []) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}

/** Create an element: el("button", {className, text, attrs, dataset, on}, [children]). */
export function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs = {}, dataset = {}, on = {} } = options;
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  for (const [name, value] of Object.entries(dataset)) node.dataset[name] = String(value);
  for (const [event, handler] of Object.entries(on)) node.addEventListener(event, handler);
  node.append(...children.filter((child) => child !== null && child !== undefined));
  return node;
}

/** Put icons into every element that names one with data-icon. */
export function hydrateIcons(root = document) {
  for (const node of root.querySelectorAll("[data-icon]")) {
    node.replaceChildren(icon(node.dataset.icon));
  }
}

/** Show a short message that disappears by itself. */
export function toast(message, { error = false, timeout = 5000 } = {}) {
  const region = document.getElementById("toasts");
  const node = el("div", { className: error ? "toast toast--error" : "toast", text: message });
  region.append(node);
  window.setTimeout(() => node.remove(), timeout);
}

/** Read a preference without failing when storage is unavailable (private mode, policies). */
export function readPreference(key, fallback) {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch {
    return fallback;
  }
}

export function writePreference(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Preferences are a convenience; the app works without them.
  }
}
