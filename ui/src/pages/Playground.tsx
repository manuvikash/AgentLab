import { useEffect, useRef, useState } from "react";
import { api } from "../api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConvRecord {
  id: string;
  agent_name: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

interface ConvMessage {
  id: number | null;
  seq: number;
  role: "user" | "assistant";
  content: string | null;
  trace: TraceEntry[];
  created_at: string;
}

interface TraceEntry {
  step: number;
  thought: string | null;
  action: string | null;
  tool_call: { tool: string; args: Record<string, unknown>; result: string } | null;
  result: string | null;
}

interface SSEStep {
  type: "thinking" | "tool_call" | "tool_result";
  step: number;
  content?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: string;
}

interface StreamingState {
  steps: SSEStep[];
  finalContent: string | null;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ToolCallCard({ step }: { step: SSEStep }) {
  const [open, setOpen] = useState(false);
  const isResult = step.type === "tool_result";
  return (
    <div className="text-xs border border-gray-200 rounded-lg overflow-hidden my-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`w-full flex items-center gap-2 px-3 py-2 text-left font-mono transition-colors ${
          isResult ? "bg-green-50 text-green-800" : "bg-yellow-50 text-yellow-800"
        }`}
      >
        <span>{isResult ? "✓" : "⚙"}</span>
        <span className="font-semibold">{step.tool}</span>
        <span className="ml-auto text-gray-400">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="p-3 bg-gray-50 font-mono text-gray-700 space-y-2">
          {step.args && (
            <div>
              <span className="text-gray-400">args: </span>
              <span className="text-blue-700">{JSON.stringify(step.args, null, 2)}</span>
            </div>
          )}
          {step.result && (
            <div>
              <span className="text-gray-400">result: </span>
              <pre className="whitespace-pre-wrap break-all text-gray-800 mt-1">
                {step.result.slice(0, 800)}
                {step.result.length > 800 ? "\n…" : ""}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StreamingBubble({ state }: { state: StreamingState }) {
  const toolPairs = state.steps.filter((s) => s.type === "tool_call" || s.type === "tool_result");

  return (
    <div className="flex gap-3 mb-4">
      <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
        A
      </div>
      <div className="flex-1 max-w-2xl">
        {toolPairs.length > 0 && (
          <div className="mb-2">
            {toolPairs.map((s, i) => (
              <ToolCallCard key={i} step={s} />
            ))}
          </div>
        )}
        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm">
          {state.finalContent !== null ? (
            <p className="text-sm text-gray-900 whitespace-pre-wrap">{state.finalContent}</p>
          ) : state.error ? (
            <p className="text-sm text-red-600">{state.error}</p>
          ) : (
            <span className="inline-flex gap-1">
              <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:300ms]" />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg }: { msg: ConvMessage }) {
  const isUser = msg.role === "user";
  const toolEntries = (msg.trace || []).filter((t) => t.tool_call !== null);

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-lg bg-indigo-600 text-white rounded-xl px-4 py-3 text-sm shadow-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 mb-4">
      <div className="w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
        A
      </div>
      <div className="flex-1 max-w-2xl">
        {toolEntries.length > 0 && (
          <div className="mb-2">
            {toolEntries.map((e, i) => (
              <ToolCallCard
                key={i}
                step={{
                  type: "tool_result",
                  step: e.step,
                  tool: e.tool_call!.tool,
                  args: e.tool_call!.args,
                  result: e.tool_call!.result,
                }}
              />
            ))}
          </div>
        )}
        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-sm">
          <p className="text-sm text-gray-900 whitespace-pre-wrap">{msg.content}</p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Playground() {
  const [agents, setAgents] = useState<{ name: string }[]>([]);
  const [conversations, setConversations] = useState<ConvRecord[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConvMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamState, setStreamState] = useState<StreamingState | null>(null);
  const [newAgentName, setNewAgentName] = useState("");
  const [showAgentPicker, setShowAgentPicker] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load agents + conversations on mount
  useEffect(() => {
    api.agents.list().then((res) => setAgents(res as { name: string }[])).catch(() => {});
    loadConversations();
  }, []);

  // Scroll to bottom on new messages or streaming update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamState]);

  function loadConversations() {
    api.conversations
      .list()
      .then((res) => setConversations(res as unknown as ConvRecord[]))
      .catch(() => {});
  }

  async function openConversation(convId: string) {
    setActiveConvId(convId);
    setStreamState(null);
    try {
      const data = (await api.conversations.get(convId)) as {
        messages: ConvMessage[];
      };
      setMessages(data.messages || []);
    } catch {
      setMessages([]);
    }
  }

  async function createConversation() {
    const name = newAgentName.trim();
    if (!name) return;
    try {
      const conv = (await api.conversations.create({ agent_name: name })) as unknown as ConvRecord;
      setConversations((prev) => [conv, ...prev]);
      setShowAgentPicker(false);
      setNewAgentName("");
      await openConversation(conv.id);
    } catch (e) {
      alert(String(e));
    }
  }

  async function deleteConversation(convId: string) {
    await api.conversations.delete(convId);
    loadConversations();
    if (activeConvId === convId) {
      setActiveConvId(null);
      setMessages([]);
    }
  }

  async function sendMessage() {
    if (!activeConvId || !input.trim() || streaming) return;

    const text = input.trim();
    setInput("");
    setStreaming(true);
    setStreamState({ steps: [], finalContent: null, error: null });

    // Optimistic user bubble
    const optimisticUser: ConvMessage = {
      id: null,
      seq: messages.length + 1,
      role: "user",
      content: text,
      trace: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser]);

    try {
      const response = await fetch(`/api/conversations/${activeConvId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let evt: Record<string, unknown>;
          try {
            evt = JSON.parse(raw);
          } catch {
            continue;
          }

          const eventType = evt.event as string;

          if (eventType === "thinking") {
            // No-op visually while streaming — final content replaces this
          } else if (eventType === "tool_call") {
            setStreamState((prev) =>
              prev
                ? {
                    ...prev,
                    steps: [
                      ...prev.steps,
                      {
                        type: "tool_call",
                        step: evt.step as number,
                        tool: evt.tool as string,
                        args: (evt.args as Record<string, unknown>) ?? {},
                      },
                    ],
                  }
                : prev
            );
          } else if (eventType === "tool_result") {
            setStreamState((prev) =>
              prev
                ? {
                    ...prev,
                    steps: [
                      ...prev.steps,
                      {
                        type: "tool_result",
                        step: evt.step as number,
                        tool: evt.tool as string,
                        result: evt.result as string,
                      },
                    ],
                  }
                : prev
            );
          } else if (eventType === "final") {
            setStreamState((prev) =>
              prev ? { ...prev, finalContent: evt.content as string } : prev
            );
          } else if (eventType === "error") {
            setStreamState((prev) =>
              prev ? { ...prev, error: evt.message as string, finalContent: "" } : prev
            );
          } else if (eventType === "done") {
            // Reload messages from server to get persisted state
            const data = (await api.conversations.get(activeConvId)) as {
              messages: ConvMessage[];
            };
            setMessages(data.messages || []);
            setStreamState(null);
            loadConversations(); // refresh titles
          }
        }
      }
    } catch (err) {
      setStreamState((prev) =>
        prev ? { ...prev, error: String(err), finalContent: "" } : prev
      );
    } finally {
      setStreaming(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  const activeConv = conversations.find((c) => c.id === activeConvId);

  return (
    <div className="flex h-full -m-6 overflow-hidden">
      {/* ── Conversation sidebar ─────────────────────────────────── */}
      <aside className="w-64 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <button
            onClick={() => setShowAgentPicker((v) => !v)}
            className="w-full flex items-center justify-center gap-2 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <span className="text-base">+</span> New Chat
          </button>

          {showAgentPicker && (
            <div className="mt-3 space-y-2">
              <select
                value={newAgentName}
                onChange={(e) => setNewAgentName(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:ring-2 focus:ring-indigo-400 outline-none"
              >
                <option value="">Select agent…</option>
                {agents.map((a) => (
                  <option key={a.name} value={a.name}>
                    {a.name}
                  </option>
                ))}
              </select>
              <button
                disabled={!newAgentName}
                onClick={createConversation}
                className="w-full py-1.5 bg-indigo-100 text-indigo-700 text-sm rounded-lg hover:bg-indigo-200 transition-colors disabled:opacity-40"
              >
                Start
              </button>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {conversations.length === 0 && (
            <p className="text-xs text-gray-400 px-4 py-6 text-center">
              No conversations yet.
              <br />
              Click "New Chat" to begin.
            </p>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              onClick={() => openConversation(c.id)}
              className={`group relative px-4 py-3 cursor-pointer transition-colors ${
                c.id === activeConvId
                  ? "bg-indigo-50 border-r-2 border-indigo-500"
                  : "hover:bg-gray-50"
              }`}
            >
              <p
                className={`text-sm font-medium truncate ${
                  c.id === activeConvId ? "text-indigo-700" : "text-gray-800"
                }`}
              >
                {c.title || "Untitled"}
              </p>
              <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                <span className="truncate">{c.agent_name}</span>
                <span>·</span>
                <span className="shrink-0">{timeAgo(c.updated_at)}</span>
              </p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteConversation(c.id);
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity text-sm p-1"
                title="Delete"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* ── Chat area ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3 shrink-0">
          {activeConv ? (
            <>
              <div>
                <p className="text-sm font-semibold text-gray-900">
                  {activeConv.title || "Untitled chat"}
                </p>
                <p className="text-xs text-gray-400">
                  Agent: <span className="text-indigo-600">{activeConv.agent_name}</span>
                </p>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-400">Select or start a conversation</p>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {!activeConvId ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-gray-400 space-y-3">
                <div className="text-5xl">💬</div>
                <p className="text-lg font-medium text-gray-500">Playground</p>
                <p className="text-sm">
                  Chat directly with any configured agent.
                  <br />
                  Tool calls and reasoning steps are shown inline.
                </p>
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <MessageBubble key={`${msg.id}-${msg.seq}`} msg={msg} />
              ))}
              {streamState && <StreamingBubble state={streamState} />}
              <div ref={bottomRef} />
            </>
          )}
        </div>

        {/* Input */}
        {activeConvId && (
          <div className="bg-white border-t border-gray-200 px-6 py-4 shrink-0">
            <div className="flex items-end gap-3">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={streaming}
                placeholder="Message the agent… (Enter to send, Shift+Enter for newline)"
                rows={1}
                className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none disabled:bg-gray-50 disabled:text-gray-400 max-h-40 overflow-y-auto"
                style={{
                  height: "auto",
                  minHeight: "44px",
                }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
                }}
              />
              <button
                onClick={sendMessage}
                disabled={streaming || !input.trim()}
                className="shrink-0 w-10 h-10 flex items-center justify-center bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {streaming ? (
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                )}
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2 text-center">
              Enter to send · Shift+Enter for newline
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
