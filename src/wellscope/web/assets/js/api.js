// Client for the WellScope HTTP API, including the server-sent-event stream of /api/chat.

export class ApiError extends Error {
  constructor(message, { status = 0, code = "error", requestId = "", retryAfter = 0 } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.retryAfter = retryAfter;
  }
}

/** A sentence for the user describing why a request failed. */
export function describeError(error) {
  if (error?.name === "AbortError") return "Stopped.";
  if (error instanceof ApiError && error.code === "rate_limited") {
    return `Too many questions in a short time. Try again in ${error.retryAfter || 10} seconds.`;
  }
  if (error instanceof ApiError) return error.message;
  return "Could not reach the WellScope server. Is it still running?";
}

/** GET a JSON resource. */
export async function getJSON(path, { signal } = {}) {
  const response = await fetch(path, { headers: { Accept: "application/json" }, signal });
  if (!response.ok) throw await toError(response);
  return response.json();
}

/**
 * Ask a question. `onStage` receives each pipeline stage; resolves with the answer event.
 * EventSource cannot POST, so the stream is read from fetch and parsed here.
 */
export async function askQuestion(body, { onStage, signal } = {}) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await toError(response);
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const event = parseEvent(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
      if (event?.name === "stage") onStage?.(event.data);
      if (event?.name === "answer") return event.data;
      if (event?.name === "error") {
        const { message, code, request_id: requestId } = event.data;
        throw new ApiError(message, { code, requestId });
      }
    }
  }
  throw new ApiError("The connection closed before an answer arrived.", { code: "stream_closed" });
}

function parseEvent(block) {
  let name = "message";
  const data = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) name = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  return data.length ? { name, data: JSON.parse(data.join("\n")) } : null;
}

async function toError(response) {
  let error = {};
  try {
    error = (await response.json()).error ?? {};
  } catch {
    // Not a JSON error envelope (for example a proxy page).
  }
  return new ApiError(error.message ?? `Request failed (${response.status}).`, {
    status: response.status,
    code: error.code ?? "http_error",
    requestId: error.request_id ?? response.headers.get("X-Request-ID") ?? "",
    retryAfter: Number(response.headers.get("Retry-After")) || 0,
  });
}
