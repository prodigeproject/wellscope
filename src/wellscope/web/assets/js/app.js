// Application controller: loads the catalog, sends questions and shows answers with sources.
import { ApiError, askQuestion, describeError, getJSON } from "./api.js";
import {
  answerCard,
  errorCard,
  glossaryItem,
  pendingAnswer,
  reportItem,
  sourceCards,
  suggestionItem,
  userMessage,
} from "./components.js";
import { el, hydrateIcons, icon, toast } from "./dom.js";
import { closeDrawers, openDrawer, openReport, wireLayout } from "./layout.js";

const MAX_HISTORY = 3;
const HISTORY_ANSWER_CHARS = 1500;
const $ = (id) => document.getElementById(id);

const state = {
  history: [],
  answers: new Map(),
  controller: null,
  glossary: [],
  emptyState: null,
};

function init() {
  state.emptyState = $("empty-state");
  hydrateIcons();
  wireLayout({ onNewChat: newConversation });
  wireComposer();
  $("thread").addEventListener("click", onThreadClick);
  $("glossary-search").addEventListener("input", (event) => renderGlossary(event.target.value));
  loadCatalog();
}

async function loadCatalog() {
  try {
    const [health, catalog, glossary] = await Promise.all([
      getJSON("/api/health"),
      getJSON("/api/catalog"),
      getJSON("/api/glossary"),
    ]);
    state.glossary = glossary.entries;
    setQuestionLimit(health.max_question_chars);
    renderCatalog(catalog);
    renderGlossary("");
    if (health.status === "no_index") {
      setStatus("No data yet. Run “wellscope ingest”, then reload.", true);
    } else if (!health.model_configured) {
      setStatus("OPENAI_API_KEY is not set, so questions cannot be answered.", true);
    } else {
      const wells = [...new Set(catalog.documents.map((doc) => doc.well).filter(Boolean))];
      const parts = [wells.join(", "), `${catalog.documents.length} reports`, `${catalog.glossary_entries} glossary terms`];
      setStatus(parts.filter(Boolean).join(" · "), false);
    }
  } catch (error) {
    setStatus("Could not reach the WellScope server.", true);
    toast(describeError(error), { error: true });
  }
}

function setQuestionLimit(limit) {
  const input = $("composer-input");
  input.setAttribute("maxlength", String(limit));
  $("char-count").textContent = `${input.value.length}/${limit}`;
}

function setStatus(text, warning) {
  const status = $("index-status");
  status.textContent = text;
  status.classList.toggle("is-warning", warning);
}

function renderCatalog(catalog) {
  $("report-list").replaceChildren(
    ...(catalog.documents.length
      ? catalog.documents.map((report) => reportItem(report, openReport))
      : [el("li", { className: "sidebar__hint", text: "No reports indexed yet." })]),
  );
  $("suggestions").replaceChildren(...catalog.suggestions.map((question) => suggestionItem(question, ask)));
}

function renderGlossary(query) {
  const needle = query.trim().toLowerCase();
  const matches = state.glossary.filter((entry) =>
    [entry.term, ...entry.aliases, entry.expansion ?? "", entry.description ?? ""].join(" ").toLowerCase().includes(needle),
  );
  $("glossary-count").textContent = `${matches.length} of ${state.glossary.length} terms`;
  $("glossary-list").replaceChildren(
    ...matches.map((entry) => glossaryItem(entry, () => ask(`What does ${entry.term} mean?`))),
  );
}

async function ask(question) {
  const text = question.trim();
  if (!text || state.controller) return;
  closeDrawers();
  state.emptyState.remove();
  const thread = $("thread");
  const pending = pendingAnswer();
  thread.append(userMessage(text), pending.node);
  scrollToEnd();
  setBusy(new AbortController());
  const progress = $("progress-status");
  try {
    const answer = await askQuestion(
      { question: text, history: state.history },
      { signal: state.controller.signal, onStage: ({ stage }) => (progress.textContent = pending.update(stage)) },
    );
    showAnswer(pending.node, answer, text);
    progress.textContent = "Answer ready.";
  } catch (error) {
    pending.node.replaceWith(errorCard(describeError(error), error.requestId));
    progress.textContent = "The question could not be answered.";
    if (error instanceof ApiError && error.code === "rate_limited") toast(describeError(error), { error: true });
  } finally {
    setBusy(null);
    scrollToEnd();
    $("composer-input").focus();
  }
}

function showAnswer(placeholder, answer, question) {
  const card = answerCard(answer, { onCopy: copyAnswer });
  card.dataset.answerId = answer.meta.request_id;
  state.answers.set(answer.meta.request_id, answer);
  placeholder.replaceWith(card);
  if (answer.status !== "error") {
    const turn = { question, answer: answer.markdown.slice(0, HISTORY_ANSWER_CHARS) };
    state.history = [...state.history, turn].slice(-MAX_HISTORY);
  }
  selectAnswer(answer.meta.request_id, null);
}

function selectAnswer(answerId, sourceId) {
  for (const card of document.querySelectorAll(".answer[data-answer-id]")) {
    card.classList.toggle("is-selected", card.dataset.answerId === answerId);
  }
  $("source-list").replaceChildren(...sourceCards(state.answers.get(answerId), sourceId, openReport));
  const card = sourceId ? $(`source-${sourceId}`) : null;
  card?.scrollIntoView({ block: "nearest" });
  card?.focus({ preventScroll: true });
}

function onThreadClick(event) {
  const target = event.target.closest("[data-source]");
  const card = event.target.closest(".answer[data-answer-id]");
  if (!target || !card) return;
  selectAnswer(card.dataset.answerId, target.dataset.source);
  if (window.matchMedia("(max-width: 1279px)").matches) openDrawer("sources");
}

async function copyAnswer(answer) {
  try {
    await navigator.clipboard.writeText(answer.markdown);
    toast("Answer copied.");
  } catch {
    toast("Copying is not available in this browser.", { error: true });
  }
}

function newConversation() {
  state.controller?.abort();
  state.history = [];
  state.answers.clear();
  $("thread").replaceChildren(state.emptyState);
  $("source-list").replaceChildren(...sourceCards(null));
  $("progress-status").textContent = "New conversation.";
  $("composer-input").focus();
}

function setBusy(controller) {
  state.controller = controller;
  const button = $("send-button");
  const label = controller ? "Stop" : "Ask";
  button.replaceChildren(icon(controller ? "stop" : "send"), el("span", { className: "button__label", text: label }));
  button.setAttribute("aria-label", controller ? "Stop answering" : "Ask");
}

function wireComposer() {
  const form = $("composer");
  const input = $("composer-input");
  const count = $("char-count");
  const resize = () => {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
    count.textContent = `${input.value.length}/${input.getAttribute("maxlength")}`;
  };
  input.addEventListener("input", resize);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      // While an answer streams, Enter keeps the draft; only the Stop button cancels.
      if (!state.controller) form.requestSubmit();
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.controller) {
      state.controller.abort();
      return;
    }
    const question = input.value;
    input.value = "";
    resize();
    ask(question);
  });
  setBusy(null);
}

function scrollToEnd() {
  const thread = $("thread");
  thread.scrollTop = thread.scrollHeight;
}

init();
