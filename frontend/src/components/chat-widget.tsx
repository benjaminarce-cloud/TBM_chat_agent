"use client";

import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import styles from "./chat-widget.module.css";

type Locale = "es" | "en";
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
};
type SessionState = { id: string; token: string; parentOrigin: string };
type SessionStatus = "connecting" | "ready" | "error" | "rate-limited";
type ConsentStatus = "idle" | "saving" | "accepted" | "error";
type FeedbackState = {
  messageId: string;
  value: "up" | "down";
  status: "saving" | "saved" | "error";
};
type ChatWidgetProps = {
  initialLocale: Locale;
  apiUrl: string;
  parentOrigin?: string;
  parentPage?: string;
  referrer?: string;
  utm: Record<string, string | undefined>;
  noticeVersion: string;
  privacyNotice: Record<Locale, string>;
};

const copy = {
  es: {
    greeting:
      "Hola, ¿en qué puedo ayudarte? Puedes preguntarme sobre envíos, servicios o cómo contactar a TBM.",
    statusReady: "Chat TBM • En línea",
    statusConnecting: "Chat TBM • Conectando",
    statusUnavailable: "Chat TBM • Sin conexión",
    placeholder: "Escribe tu mensaje…",
    send: "Enviar mensaje",
    connecting: "Conectando de forma segura…",
    connectionTitle: "No pudimos conectar el chat",
    connectionBody:
      "Revisa tu conexión e inténtalo de nuevo. Si el problema continúa, contacta al equipo de TBM por el canal habitual.",
    sessionRate:
      "Se alcanzó el límite de conexiones. Espera un momento antes de volver a intentarlo.",
    retry: "Reintentar conexión",
    error: "No pude completar esa respuesta. Un especialista de TBM puede continuar contigo.",
    streamInterrupted: "La conexión se interrumpió. Puedes volver a intentarlo.",
    emptyResponse: "No recibí una respuesta. Inténtalo de nuevo o solicita hablar con ventas.",
    rate: "Has enviado mensajes muy rápido. Espera un momento e inténtalo de nuevo.",
    noticeTitle: "Aviso de privacidad",
    accept: "Aceptar aviso",
    accepting: "Guardando aceptación…",
    accepted: "Aviso aceptado",
    consentError: "No se pudo guardar tu aceptación. Inténtalo de nuevo.",
    feedback: "¿Te ayudó esta respuesta?",
    feedbackUp: "Sí",
    feedbackDown: "No",
    helpful: "Sí, fue útil",
    notHelpful: "No fue útil",
    feedbackThanks: "Gracias por tus comentarios.",
    feedbackError: "No se pudo enviar. Inténtalo de nuevo.",
    typing: "TBM está escribiendo",
    ended: "Este chat llegó a su límite. Un especialista de TBM puede continuar contigo.",
    disclaimer: "Piloto • TBM no proporciona tarifas en el chat",
    suggestions: ["Quiero solicitar una cotización", "Quiero hablar con ventas"],
  },
  en: {
    greeting:
      "Hi, how can I help? Ask me about shipping, TBM services, or how to get in touch with the team.",
    statusReady: "TBM chat • Online",
    statusConnecting: "TBM chat • Connecting",
    statusUnavailable: "TBM chat • Connection unavailable",
    placeholder: "Type your message…",
    send: "Send message",
    connecting: "Connecting securely…",
    connectionTitle: "We couldn’t connect the chat",
    connectionBody:
      "Check your connection and try again. If the problem continues, contact the TBM team through the usual channel.",
    sessionRate: "The connection limit was reached. Wait a moment before trying again.",
    retry: "Retry connection",
    error: "I couldn’t complete that response. A TBM specialist can continue with you.",
    streamInterrupted: "The connection was interrupted. You can try again.",
    emptyResponse: "I didn’t receive a response. Try again or ask to speak with sales.",
    rate: "You’re sending messages too quickly. Wait a moment and try again.",
    noticeTitle: "Privacy notice",
    accept: "Accept notice",
    accepting: "Saving acceptance…",
    accepted: "Notice accepted",
    consentError: "We couldn’t save your acceptance. Please try again.",
    feedback: "Was this response helpful?",
    feedbackUp: "Yes",
    feedbackDown: "No",
    helpful: "Yes, this was helpful",
    notHelpful: "This was not helpful",
    feedbackThanks: "Thanks for your feedback.",
    feedbackError: "We couldn’t send it. Please try again.",
    typing: "TBM is typing",
    ended: "This chat reached its limit. A TBM specialist can continue with you.",
    disclaimer: "Pilot • TBM does not provide rates in chat",
    suggestions: ["I want to request a quote", "I want to speak with sales"],
  },
} as const;

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function exactOrigin(value: string | undefined, fallback: string) {
  try {
    const parsed = new URL(value ?? fallback);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.origin
      : fallback;
  } catch {
    return fallback;
  }
}

const inlineMarkdownPattern =
  /(\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*([^*\n]+)\*|_([^_\n]+)_)/g;

function renderInlineMarkdown(value: string) {
  const output: ReactNode[] = [];
  let cursor = 0;

  for (const match of value.matchAll(inlineMarkdownPattern)) {
    const index = match.index ?? 0;
    if (index > cursor) output.push(value.slice(cursor, index));

    if (match[2] || match[3]) {
      output.push(<strong key={index}>{match[2] ?? match[3]}</strong>);
    } else if (match[4]) {
      output.push(<code key={index}>{match[4]}</code>);
    } else if (match[5] && match[6]) {
      output.push(
        <a key={index} href={match[6]} target="_blank" rel="noreferrer noopener">
          {match[5]}
        </a>,
      );
    } else if (match[7] || match[8]) {
      output.push(<em key={index}>{match[7] ?? match[8]}</em>);
    }
    cursor = index + match[0].length;
  }

  if (cursor < value.length) output.push(value.slice(cursor));
  return output;
}

type MessageBlock =
  | { type: "paragraph"; content: string }
  | { type: "heading"; content: string }
  | { type: "quote"; content: string }
  | { type: "ordered"; items: string[]; start?: number }
  | { type: "unordered"; items: string[] };

function parseMessageBlocks(content: string) {
  const lines = content.replace(/\r\n/g, "\n").trim().split("\n");
  const blocks: MessageBlock[] = [];
  let index = 0;

  const isBlockStart = (line: string) =>
    /^(?:#{1,3}\s+|>\s*|\d+[.)]\s+|[-*•]\s+)/.test(line.trim());

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      blocks.push({ type: "heading", content: heading[1] });
      index += 1;
      continue;
    }

    if (line.startsWith(">")) {
      const quote: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quote.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push({ type: "quote", content: quote.join(" ") });
      continue;
    }

    const ordered = line.match(/^(\d+)[.)]\s+(.+)$/);
    const unordered = line.match(/^[-*•]\s+(.+)$/);
    if (ordered || unordered) {
      const type = ordered ? "ordered" : "unordered";
      const items: string[] = [];
      const start = ordered ? Number(ordered[1]) : undefined;

      while (index < lines.length) {
        const current = lines[index].trim();
        const currentItem =
          type === "ordered"
            ? current.match(/^\d+[.)]\s+(.+)$/)
            : current.match(/^[-*•]\s+(.+)$/);
        if (currentItem) {
          items.push(currentItem[1]);
          index += 1;
          continue;
        }
        if (current && !isBlockStart(current) && items.length > 0) {
          items[items.length - 1] += ` ${current}`;
          index += 1;
          continue;
        }
        break;
      }

      blocks.push({ type, items, start });
      continue;
    }

    const paragraph = [line];
    index += 1;
    while (index < lines.length) {
      const next = lines[index].trim();
      if (!next || isBlockStart(next)) break;
      paragraph.push(next);
      index += 1;
    }
    blocks.push({ type: "paragraph", content: paragraph.join(" ") });
  }

  return blocks;
}

function FormattedMessage({ content }: { content: string }) {
  return (
    <div className={styles.messageContent}>
      {parseMessageBlocks(content).map((block, index) => {
        if (block.type === "ordered" || block.type === "unordered") {
          const List = block.type === "ordered" ? "ol" : "ul";
          return (
            <List key={index} start={block.type === "ordered" ? block.start : undefined}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
              ))}
            </List>
          );
        }
        if (block.type === "heading") {
          return (
            <p key={index} className={styles.messageHeading}>
              {renderInlineMarkdown(block.content)}
            </p>
          );
        }
        if (block.type === "quote") {
          return <blockquote key={index}>{renderInlineMarkdown(block.content)}</blockquote>;
        }
        return <p key={index}>{renderInlineMarkdown(block.content)}</p>;
      })}
    </div>
  );
}

export default function ChatWidget({
  initialLocale,
  apiUrl,
  parentOrigin,
  parentPage,
  referrer,
  utm,
  noticeVersion,
  privacyNotice,
}: ChatWidgetProps) {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [session, setSession] = useState<SessionState | null>(null);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("connecting");
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: makeId(), role: "assistant", content: copy[initialLocale].greeting },
  ]);
  const [draft, setDraft] = useState("");
  const [consentStatus, setConsentStatus] = useState<ConsentStatus>("idle");
  const [busy, setBusy] = useState(false);
  const [conversationEnded, setConversationEnded] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const text = copy[locale];

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    const embeddingOrigin =
      window.self !== window.top ? exactOrigin(document.referrer, "") : "";
    const resolvedParentOrigin =
      embeddingOrigin || exactOrigin(parentOrigin, window.location.origin);

    void fetch(`${apiUrl}/api/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        locale: initialLocale,
        parent_origin: resolvedParentOrigin,
        source: {
          page: parentPage,
          referrer,
          utm,
        },
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(response.status === 429 ? "rate-limited" : "session-failed");
        }
        return response.json() as Promise<{ session_id: string; widget_token: string }>;
      })
      .then((data) => {
        setSession({
          id: data.session_id,
          token: data.widget_token,
          parentOrigin: resolvedParentOrigin,
        });
        setSessionStatus("ready");
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted && error instanceof DOMException && error.name === "AbortError") {
          setSessionStatus("error");
          return;
        }
        setSessionStatus(
          error instanceof Error && error.message === "rate-limited" ? "rate-limited" : "error",
        );
      })
      .finally(() => window.clearTimeout(timeout));

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [apiUrl, initialLocale, parentOrigin, parentPage, referrer, sessionAttempt, utm]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, consentStatus, requestError]);

  const latestAssistantId = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant")?.id,
    [messages],
  );

  const statusText =
    sessionStatus === "ready"
      ? text.statusReady
      : sessionStatus === "connecting"
        ? text.statusConnecting
        : text.statusUnavailable;

  function authHeaders() {
    return {
      Authorization: `Bearer ${session?.token ?? ""}`,
      "Content-Type": "application/json",
      "X-Widget-Origin": session?.parentOrigin ?? "",
    };
  }

  function changeLocale(nextLocale: Locale) {
    setLocale(nextLocale);
    setMessages((current) =>
      current.length === 1 && current[0].role === "assistant"
        ? [{ ...current[0], content: copy[nextLocale].greeting }]
        : current,
    );
  }

  function retrySession() {
    setSession(null);
    setSessionStatus("connecting");
    setConsentStatus("idle");
    setConversationEnded(false);
    setRequestError(null);
    setSessionAttempt((current) => current + 1);
  }

  async function acceptConsent() {
    if (!session || consentStatus === "saving" || consentStatus === "accepted") return;
    setConsentStatus("saving");
    try {
      const response = await fetch(`${apiUrl}/api/session/${session.id}/consent`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          notice_version: noticeVersion,
          locale,
          cross_border_ack: true,
        }),
      });
      if (!response.ok) throw new Error("consent-failed");
      setConsentStatus("accepted");
    } catch {
      setConsentStatus("error");
    }
  }

  async function sendMessage(value = draft) {
    const content = value.trim();
    if (!content || !session || busy || conversationEnded || consentStatus !== "accepted") return;
    setDraft("");
    setBusy(true);
    setFeedback(null);
    setRequestError(null);
    const assistantId = makeId();
    setMessages((current) => [
      ...current,
      { id: makeId(), role: "user", content },
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);

    let receivedText = "";
    try {
      const response = await fetch(`${apiUrl}/api/session/${session.id}/message`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ content }),
      });
      if (!response.ok || !response.body) {
        throw new Error(response.status === 429 ? "rate-limited" : "request-failed");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const processFrame = (frame: string) => {
        const event = frame
          .split("\n")
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim();
        const rawData = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!rawData) return;

        const data = JSON.parse(rawData) as { text?: unknown; capped?: unknown };
        if (event === "token" && typeof data.text === "string") {
          receivedText += data.text;
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? { ...message, content: message.content + data.text }
                : message,
            ),
          );
        }
        if (event === "done" && data.capped === true) {
          setConversationEnded(true);
        }
      };

      while (true) {
        const { done, value: chunk } = await reader.read();
        buffer += decoder.decode(chunk, { stream: !done }).replace(/\r\n/g, "\n");
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        frames.filter(Boolean).forEach(processFrame);
        if (done) break;
      }
      if (buffer.trim()) processFrame(buffer);

      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: message.content || copy[locale].emptyResponse,
                streaming: false,
              }
            : message,
        ),
      );
    } catch (error) {
      const isRateLimit = error instanceof Error && error.message === "rate-limited";
      const fallbackMessage = isRateLimit ? copy[locale].rate : copy[locale].error;
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId
            ? {
                ...item,
                content: item.content || fallbackMessage,
                streaming: false,
              }
            : item,
        ),
      );
      if (receivedText) setRequestError(copy[locale].streamInterrupted);
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(messageId: string, thumbs: "up" | "down") {
    if (!session || feedback?.status === "saving") return;
    setFeedback({ messageId, value: thumbs, status: "saving" });
    try {
      const response = await fetch(`${apiUrl}/api/session/${session.id}/feedback`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ thumbs }),
      });
      if (!response.ok) throw new Error("feedback-failed");
      setFeedback({ messageId, value: thumbs, status: "saved" });
    } catch {
      setFeedback({ messageId, value: thumbs, status: "error" });
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void sendMessage();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void sendMessage();
    }
  }

  return (
    <main className={styles.widget} lang={locale}>
      <header className={styles.header}>
        <div className={styles.identity}>
          <span className={styles.mark}>TBM</span>
          <span>
            <strong>TBM Carriers</strong>
            <small>
              <span
                className={`${styles.statusDot} ${sessionStatus === "ready" ? styles.online : ""}`}
                aria-hidden="true"
              />
              {statusText}
            </small>
          </span>
        </div>
        <div className={styles.localeSwitch} aria-label="Language / Idioma">
          <button
            type="button"
            className={locale === "es" ? styles.activeLocale : ""}
            onClick={() => changeLocale("es")}
            aria-pressed={locale === "es"}
            disabled={busy}
          >
            ES
          </button>
          <button
            type="button"
            className={locale === "en" ? styles.activeLocale : ""}
            onClick={() => changeLocale("en")}
            aria-pressed={locale === "en"}
            disabled={busy}
          >
            EN
          </button>
        </div>
      </header>

      <section className={styles.messages} aria-live="polite" aria-label="Conversation">
        {sessionStatus === "connecting" && (
          <div className={styles.connecting} role="status">
            <span className={styles.spinner} aria-hidden="true" />
            {text.connecting}
          </div>
        )}

        {(sessionStatus === "error" || sessionStatus === "rate-limited") && (
          <div className={styles.connectionCard} role="alert">
            <span className={styles.connectionIcon} aria-hidden="true">
              !
            </span>
            <div>
              <strong>{text.connectionTitle}</strong>
              <p>
                {sessionStatus === "rate-limited" ? text.sessionRate : text.connectionBody}
              </p>
              <button type="button" onClick={retrySession}>
                {text.retry}
              </button>
            </div>
          </div>
        )}

        {messages.map((message, index) => {
          const messageFeedback = feedback?.messageId === message.id ? feedback : null;
          return (
            <div key={message.id} className={`${styles.messageRow} ${styles[message.role]}`}>
              {message.role === "assistant" && <span className={styles.avatar}>T</span>}
              <div className={styles.messageBody}>
                <div className={styles.bubble}>
                  {message.content ? (
                    message.role === "assistant" ? (
                      <FormattedMessage content={message.content} />
                    ) : (
                      message.content
                    )
                  ) : (
                    <span className={styles.typing} role="status" aria-label={text.typing} />
                  )}
                </div>
                {message.id === latestAssistantId && !message.streaming && index > 0 && (
                  <div className={styles.feedback}>
                    {messageFeedback?.status === "saved" ? (
                      <span className={styles.feedbackResult}>✓ {text.feedbackThanks}</span>
                    ) : (
                      <>
                        <span>{text.feedback}</span>
                        <button
                          type="button"
                          onClick={() => void sendFeedback(message.id, "up")}
                          aria-label={text.helpful}
                          aria-pressed={messageFeedback?.value === "up"}
                          className={messageFeedback?.value === "up" ? styles.selectedFeedback : ""}
                          disabled={messageFeedback?.status === "saving"}
                        >
                          {text.feedbackUp}
                        </button>
                        <button
                          type="button"
                          onClick={() => void sendFeedback(message.id, "down")}
                          aria-label={text.notHelpful}
                          aria-pressed={messageFeedback?.value === "down"}
                          className={messageFeedback?.value === "down" ? styles.selectedFeedback : ""}
                          disabled={messageFeedback?.status === "saving"}
                        >
                          {text.feedbackDown}
                        </button>
                        {messageFeedback?.status === "error" && (
                          <span className={styles.inlineError}>{text.feedbackError}</span>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {messages.length === 1 && sessionStatus === "ready" && consentStatus === "accepted" && (
          <div className={styles.suggestions} aria-label="Suggested messages">
            {text.suggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => void sendMessage(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {requestError && (
          <p className={styles.requestError} role="alert">
            {requestError}
          </p>
        )}

        {consentStatus !== "accepted" ? (
          <aside className={styles.consent} aria-labelledby="consent-title">
            <div>
              <span className={styles.shield} aria-hidden="true">
                •
              </span>
              <div>
                <strong id="consent-title">{text.noticeTitle}</strong>
                <p>{privacyNotice[locale]}</p>
              </div>
            </div>
            {consentStatus === "error" && (
              <p className={styles.consentError} role="alert">
                {text.consentError}
              </p>
            )}
            <button
              type="button"
              onClick={() => void acceptConsent()}
              disabled={!session || consentStatus === "saving"}
            >
              {consentStatus === "saving" ? text.accepting : text.accept}
            </button>
          </aside>
        ) : (
          <p className={styles.accepted}>✓ {text.accepted}</p>
        )}

        {conversationEnded && (
          <p className={styles.ended} role="status">
            {text.ended}
          </p>
        )}
        <div ref={bottomRef} />
      </section>

      <form className={styles.composer} onSubmit={onSubmit}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value.slice(0, 2000))}
          onKeyDown={onKeyDown}
          placeholder={conversationEnded ? text.ended : text.placeholder}
          aria-label={text.placeholder}
          rows={1}
          disabled={!session || busy || conversationEnded || consentStatus !== "accepted"}
        />
        <button
          type="submit"
          disabled={
            !draft.trim() ||
            !session ||
            busy ||
            conversationEnded ||
            consentStatus !== "accepted"
          }
          aria-label={text.send}
        >
          <span aria-hidden="true">↑</span>
        </button>
      </form>
      <p className={styles.disclaimer}>{text.disclaimer}</p>
    </main>
  );
}
