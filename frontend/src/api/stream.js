import { createParser } from "eventsource-parser";

async function consume(response, onEvent) {
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const runId = response.headers.get("x-run-id");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createParser({
    onEvent(event) {
      onEvent(event.event, JSON.parse(event.data));
    },
  });
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    parser.feed(decoder.decode(value, { stream: true }));
  }
  return runId;
}

export async function startRun(request, onEvent) {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return consume(response, onEvent);
}

export async function submitApproval(runId, decision, onEvent) {
  const response = await fetch(`/api/runs/${runId}/approval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(decision),
  });
  return consume(response, onEvent);
}