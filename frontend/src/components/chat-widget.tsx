"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import styles from "./chat-widget.module.css";

type Locale = "es" | "en";
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
};
type SessionState = { id: string; token: string };
type ChatWidgetProps = {
  initialLocale: Locale;
  apiUrl: string;
  parentOrigin: string;
  parentPage?: string;
  referrer?: string;
  utm: Record<string, string | undefined>;
};

const NOTICE_VERSION = "pilot-placeholder-v0-legal-review-required";

const copy = {
  es: {
    greeting: "Hola, soy el asistente de TBM. ¿Qué necesitas transportar y entre qué ciudades?",
    status: "Asistente de ventas • En línea",
    placeholder: "Escribe tu mensaje…",
    send: "Enviar mensaje",
    connecting: "Conectando de forma segura…",
    error: "No pude completar esa respuesta. Un especialista de TBM puede continuar contigo.",
    rate: "Has enviado mensajes muy rápido. Espera un momento e inténtalo de nuevo.",
    noticeTitle: "Aviso de privacidad pendiente de revisión legal",
    notice:
      "[MARCADOR LEGAL — TBM/asesoría debe proporcionar el texto aprobado en español que cubra: finalidad de calificación y seguimiento; transferencia/almacenamiento en EE. UU.; minimización de datos; y contacto para derechos ARCO.]",
    accept: "Aceptar aviso piloto",
    accepted: "Aviso piloto aceptado",
    feedback: "¿Te ayudó esta respuesta?",
    suggestions: ["Quiero solicitar una cotización", "Quiero hablar con ventas"],
  },
  en: {
    greeting: "Hi, I’m TBM’s assistant. What do you need to ship, and between which cities?",
    status: "Sales assistant • Online",
    placeholder: "Type your message…",
    send: "Send message",
    connecting: "Connecting securely…",
    error: "I couldn’t complete that response. A TBM specialist can continue with you.",
    rate: "You’re sending messages too quickly. Wait a moment and try again.",
    noticeTitle: "Privacy notice pending legal review",
    notice:
      "[LEGAL PLACEHOLDER — TBM/counsel must provide approved English copy covering: qualification/follow-up purpose; US transfer/storage; data minimization; and an ARCO-rights contact.]",
    accept: "Accept pilot notice",
    accepted: "Pilot notice accepted",
    feedback: "Was this response helpful?",
    suggestions: ["I want to request a quote", "I want to speak with sales"],
  },
} as const;

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function ChatWidget({
  initialLocale,
  apiUrl,
  parentOrigin,
  parentPage,
  referrer,
  utm,
}: ChatWidgetProps) {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [session, setSession] = useState<SessionState | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: makeId(), role: "assistant", content: copy[initialLocale].greeting },
  ]);
  const [draft, setDraft] = useState("");
  const [consented, setConsented] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const text = copy[locale];

  useEffect(() => {
    fetch(`${apiUrl}/api/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        locale: initialLocale,
        parent_origin: parentOrigin,
        source: {
          page: parentPage,
          referrer,
          utm,
        },
      }),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("session failed");
        return response.json();
      })
      .then((data) => setSession({ id: data.session_id, token: data.widget_token }))
      .catch(() => setSession(null));
  }, [apiUrl, initialLocale, parentOrigin, parentPage, referrer, utm]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, consented]);

  const latestAssistantId = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant")?.id,
    [messages],
  );

  function authHeaders() {
    return {
      Authorization: `Bearer ${session?.token ?? ""}`,
      "Content-Type": "application/json",
      "X-Widget-Origin": parentOrigin,
    };
  }

  async function acceptConsent() {
    if (!session || consented) return;
    const response = await fetch(`${apiUrl}/api/session/${session.id}/consent`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({
        notice_version: NOTICE_VERSION,
        locale,
        cross_border_ack: true,
      }),
    });
    if (response.ok) setConsented(true);
  }

  async function sendMessage(value = draft) {
    const content = value.trim();
    if (!content || !session || busy) return;
    setDraft("");
    setBusy(true);
    setFeedback(null);
    const assistantId = makeId();
    setMessages((current) => [
      ...current,
      { id: makeId(), role: "user", content },
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);

    try {
      const response = await fetch(`${apiUrl}/api/session/${session.id}/message`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ content }),
      });
      if (!response.ok || !response.body) {
        throw new Error(response.status === 429 ? "rate" : "request");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value: chunk } = await reader.read();
        if (done) break;
        buffer += decoder.decode(chunk, { stream: true }).replace(/\r\n/g, "\n");
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const event = frame.match(/^event:\s*(.+)$/m)?.[1];
          const data = frame.match(/^data:\s*(.+)$/m)?.[1];
          if (event === "token" && data) {
            const token = JSON.parse(data).text as string;
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + token }
                  : message,
              ),
            );
          }
        }
      }
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId ? { ...message, streaming: false } : message,
        ),
      );
    } catch (error) {
      const message = error instanceof Error && error.message === "rate" ? text.rate : text.error;
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId ? { ...item, content: message, streaming: false } : item,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(thumbs: "up" | "down") {
    if (!session || feedback) return;
    setFeedback(thumbs);
    await fetch(`${apiUrl}/api/session/${session.id}/feedback`, {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ thumbs }),
    }).catch(() => undefined);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void sendMessage();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  }

  return (
    <main className={styles.widget}>
      <header className={styles.header}>
        <div className={styles.identity}>
          <span className={styles.mark}>TBM</span>
          <span>
            <strong>TBM Carriers</strong>
            <small>{text.status}</small>
          </span>
        </div>
        <div className={styles.localeSwitch} aria-label="Language / Idioma">
          <button
            type="button"
            className={locale === "es" ? styles.activeLocale : ""}
            onClick={() => setLocale("es")}
          >
            ES
          </button>
          <button
            type="button"
            className={locale === "en" ? styles.activeLocale : ""}
            onClick={() => setLocale("en")}
          >
            EN
          </button>
        </div>
      </header>

      <section className={styles.messages} aria-live="polite" aria-label="Conversation">
        {!session && <p className={styles.connecting}>{text.connecting}</p>}
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={`${styles.messageRow} ${styles[message.role]}`}
          >
            {message.role === "assistant" && <span className={styles.avatar}>T</span>}
            <div>
              <div className={styles.bubble}>
                {message.content || <span className={styles.typing} aria-label="Typing" />}
              </div>
              {message.id === latestAssistantId &&
                !message.streaming &&
                index > 0 &&
                !feedback && (
                  <div className={styles.feedback}>
                    <span>{text.feedback}</span>
                    <button type="button" onClick={() => void sendFeedback("up")} aria-label="Helpful">
                      ↑
                    </button>
                    <button type="button" onClick={() => void sendFeedback("down")} aria-label="Not helpful">
                      ↓
                    </button>
                  </div>
                )}
            </div>
          </div>
        ))}

        {messages.length === 1 && session && (
          <div className={styles.suggestions}>
            {text.suggestions.map((suggestion) => (
              <button key={suggestion} type="button" onClick={() => void sendMessage(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {!consented ? (
          <aside className={styles.consent} aria-labelledby="consent-title">
            <div>
              <span className={styles.shield} aria-hidden="true">
                •
              </span>
              <div>
                <strong id="consent-title">{text.noticeTitle}</strong>
                <p>{text.notice}</p>
              </div>
            </div>
            <button type="button" onClick={() => void acceptConsent()} disabled={!session}>
              {text.accept}
            </button>
          </aside>
        ) : (
          <p className={styles.accepted}>✓ {text.accepted}</p>
        )}
        <div ref={bottomRef} />
      </section>

      <form className={styles.composer} onSubmit={onSubmit}>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value.slice(0, 2000))}
          onKeyDown={onKeyDown}
          placeholder={text.placeholder}
          aria-label={text.placeholder}
          rows={1}
          disabled={!session || busy}
        />
        <button type="submit" disabled={!draft.trim() || !session || busy} aria-label={text.send}>
          ↑
        </button>
      </form>
      <p className={styles.disclaimer}>Pilot • TBM does not provide prices in chat</p>
    </main>
  );
}
