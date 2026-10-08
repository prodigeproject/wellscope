// View components: plain functions that build DOM nodes from API data.
import { el, icon } from "./dom.js";

const STATUS = {
  answered: { label: "Answered", icon: "check" },
  unverified: { label: "Unverified figures", icon: "alert" },
  not_found: { label: "Not in the documents", icon: "info" },
  out_of_scope: { label: "Out of scope", icon: "ban" },
  error: { label: "Error", icon: "alert" },
};
export const STAGES = [
  ["analyzing", "Understanding the question"],
  ["retrieving", "Finding sources"],
  ["composing", "Writing the answer"],
  ["verifying", "Checking citations and figures"],
];
const DOC_BADGES = { DDR: "doc-badge", DGOS: "doc-badge doc-badge--dgos" };
const SYNTHETIC_SOURCES = new Set(["glossary", "catalog", "conflicts"]);
const NUMBER = /\d[\d.,:/-]*\d|\d/g;

export function reportItem(report, onOpen) {
  const quality =
    report.quality_status === "ok"
      ? null
      : el("span", { className: "report__quality", attrs: { title: "This report has data-quality notes" } }, [
          icon("alert"),
          el("span", { text: "notes" }),
        ]);
  const period = report.period ? `Covers ${report.period}` : report.title;
  return el("li", {}, [
    el(
      "button",
      {
        className: "report",
        attrs: { type: "button", "aria-label": `${report.label}. ${period}. Open the full report` },
        on: { click: () => onOpen(report.doc_id) },
      },
      [
        el("span", { className: DOC_BADGES[report.doc_type] ?? "doc-badge", text: report.doc_type }),
        el("span", { className: "report__label" }, [
          el("span", { text: report.report_number === null ? report.title : `#${report.report_number}` }),
          el("span", { className: "report__date", text: report.report_date ?? "" }),
        ]),
        quality,
        el("span", { className: "report__period", text: period }),
      ],
    ),
  ]);
}

export function glossaryItem(entry, onAsk) {
  const status =
    entry.status === "confirmed"
      ? null
      : el("span", {
          className: "term__status",
          text: entry.status === "unknown" ? "meaning unknown" : "to be confirmed",
        });
  return el("li", {}, [
    el(
      "button",
      {
        className: "term",
        attrs: { type: "button", title: `Ask what ${entry.term} means` },
        on: { click: () => onAsk(entry) },
      },
      [
        el("span", { className: "term__name", text: entry.term }),
        status,
        el("span", {
          className: "term__meaning",
          text: entry.expansion ?? entry.description ?? "Meaning not stated in the glossary",
        }),
      ],
    ),
  ]);
}

export function suggestionItem(question, onPick) {
  return el("li", {}, [
    el("button", {
      className: "suggestion",
      text: question,
      attrs: { type: "button" },
      on: { click: () => onPick(question) },
    }),
  ]);
}

export function userMessage(text) {
  return el("div", { className: "message message--user" }, [el("p", { className: "bubble", text })]);
}

/** A placeholder answer that shows pipeline progress; returns the node and an updater. */
export function pendingAnswer() {
  const steps = STAGES.map(([stage, label]) => el("li", { className: "step", text: label, dataset: { stage } }));
  const node = el("article", { className: "message answer", attrs: { "aria-busy": "true" } }, [
    el("header", { className: "answer__header" }, [el("span", { className: "answer__author", text: "WellScope" })]),
    el("ol", { className: "stepper", attrs: { "aria-label": "Progress" } }, steps),
  ]);
  const update = (stage) => {
    const current = STAGES.findIndex(([name]) => name === stage);
    steps.forEach((step, index) => {
      step.classList.toggle("is-done", index < current);
      step.classList.toggle("is-active", index === current);
    });
    return STAGES[current]?.[1] ?? "";
  };
  return { node, update };
}

export function answerCard(answer, { onCopy }) {
  const status = answer.status === "answered" && !answer.verified ? "unverified" : answer.status;
  const { label, icon: statusIcon } = STATUS[status] ?? STATUS.error;
  const body = el("div", { className: "answer__body prose" });
  // Server-rendered: Markdown with raw HTML disabled, then an allow-list sanitiser (nh3).
  body.innerHTML = answer.html;
  return el("article", { className: "message answer", attrs: { "aria-label": `Answer, ${label}` } }, [
    el("header", { className: "answer__header" }, [
      el("span", { className: "answer__author", text: "WellScope" }),
      el("span", { className: `badge badge--${status}` }, [icon(statusIcon), el("span", { text: label })]),
    ]),
    body,
    caveatList(answer.caveats),
    citationList(answer.citations),
    el("footer", { className: "answer__meta" }, [
      el("span", { className: "tabular", text: `${(answer.meta.latency_ms / 1000).toFixed(1)} s` }),
      answer.meta.models.length ? el("span", { text: answer.meta.models.at(-1) }) : null,
      el("button", { className: "button button--small", attrs: { type: "button" }, on: { click: () => onCopy(answer) } }, [
        icon("copy"),
        el("span", { text: "Copy" }),
      ]),
    ]),
  ]);
}

export function errorCard(message, requestId) {
  return el("article", { className: "message answer", attrs: { "aria-label": "Answer, error" } }, [
    el("header", { className: "answer__header" }, [
      el("span", { className: "answer__author", text: "WellScope" }),
      el("span", { className: "badge badge--error" }, [icon("alert"), el("span", { text: "Error" })]),
    ]),
    el("p", { text: message }),
    requestId ? el("p", { className: "answer__meta", text: `Reference: ${requestId}` }) : null,
  ]);
}

function caveatList(caveats) {
  if (!caveats.length) return null;
  return el("aside", { className: "callout", attrs: { "aria-label": "Notes on this answer" } }, [
    icon("alert"),
    el("ul", {}, caveats.map((text) => el("li", { text }))),
  ]);
}

function citationList(citations) {
  if (!citations.length) return null;
  return el(
    "ul",
    { className: "citations", attrs: { "aria-label": "Sources cited" } },
    citations.map((citation) =>
      el("li", {}, [
        el(
          "button",
          {
            className: "chip",
            attrs: { type: "button", "aria-label": `Show source ${citation.id}: ${describe(citation)}` },
            dataset: { source: citation.id },
          },
          [el("span", { className: "chip__id", text: citation.id }), el("span", { className: "chip__text", text: describe(citation) })],
        ),
      ]),
    ),
  );
}

function describe(citation) {
  const page = citation.page ? ` · p.${citation.page}` : "";
  return `${citation.label} · ${citation.section}${page}`;
}

/** Sources of one answer, with the figures the answer quotes highlighted. */
export function sourceCards(answer, activeId, onOpenReport) {
  if (!answer) return [el("p", { className: "sources__empty", text: "Select a citation in an answer to see the exact passage here." })];
  if (!answer.citations.length) return [el("p", { className: "sources__empty", text: "This answer cites no sources." })];
  const quoted = new Set(answer.markdown.match(NUMBER) ?? []);
  return answer.citations.map((citation) => {
    const meta = [citation.section, citation.page ? `page ${citation.page}` : "", citation.period ? `covers ${citation.period}` : ""];
    return el(
      "article",
      {
        className: citation.id === activeId ? "source-card is-active" : "source-card",
        attrs: { id: `source-${citation.id}`, tabindex: "-1", "aria-label": `Source ${citation.id}` },
      },
      [
        el("header", { className: "source-card__head" }, [
          el("span", { className: "chip__id", text: citation.id }),
          el("span", { text: citation.label }),
        ]),
        el("p", { className: "source-card__meta", text: meta.filter(Boolean).join(" · ") }),
        excerpt(citation.excerpt, quoted),
        SYNTHETIC_SOURCES.has(citation.doc_id)
          ? null
          : el("button", { className: "button button--small", attrs: { type: "button" }, on: { click: () => onOpenReport(citation.doc_id) } }, [
              icon("external"),
              el("span", { text: "Open full report" }),
            ]),
      ],
    );
  });
}

function excerpt(text, quoted) {
  const node = el("p", { className: "excerpt" });
  let last = 0;
  for (const match of text.matchAll(NUMBER)) {
    if (!quoted.has(match[0])) continue;
    node.append(text.slice(last, match.index), el("mark", { text: match[0] }));
    last = match.index + match[0].length;
  }
  node.append(text.slice(last));
  return node;
}
