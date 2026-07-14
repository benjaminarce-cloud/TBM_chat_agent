import Script from "next/script";
import styles from "./page.module.css";

const apiUrl = process.env.NEXT_PUBLIC_CHAT_API_URL ?? "http://localhost:8000";

export default function Home() {
  return (
    <main className={styles.siteShell}>
      <nav className={styles.nav} aria-label="Demo site navigation">
        <a href="#top" className={styles.brand} aria-label="TBM Carriers demo home">
          <span className={styles.brandMark}>TBM</span>
          <span>
            <strong>TBM Carriers</strong>
            <small>Cross-border freight</small>
          </span>
        </a>
        <div className={styles.navLinks}>
          <a href="#services">Services</a>
          <a href="#network">Network</a>
          <a href="#contact">Contact</a>
        </div>
        <a className={styles.navCta} href="#contact">
          Talk to sales
        </a>
      </nav>

      <section className={styles.hero} id="top">
        <div className={styles.eyebrow}>
          <span aria-hidden="true" />
          Pilot embed environment
        </div>
        <h1>
          Freight moves fast.
          <br />
          <em>Your answers should too.</em>
        </h1>
        <p>
          This standalone page demonstrates the TBM bilingual inbound sales agent in the
          same one-script format used on a host website.
        </p>
        <div className={styles.heroActions}>
          <button
            className={styles.primaryAction}
            type="button"
            data-tbm-chat-open
            aria-describedby="chat-hint"
          >
            Open the chat at lower right
          </button>
          <span id="chat-hint">English / Español</span>
        </div>
      </section>

      <section className={styles.statStrip} aria-label="Pilot principles">
        <article>
          <span>01</span>
          <h2>Qualify</h2>
          <p>Capture the lane, freight, timeline, and contact route.</p>
        </article>
        <article>
          <span>02</span>
          <h2>Protect</h2>
          <p>Consent-aware storage and independent pricing guardrails.</p>
        </article>
        <article>
          <span>03</span>
          <h2>Handoff</h2>
          <p>Route a useful lead summary to a human sales specialist.</p>
        </article>
      </section>

      <section className={styles.demoNote} id="services">
        <div>
          <span className={styles.noteIndex}>ABOUT THIS PAGE</span>
          <h2>A safe place to validate the full visitor flow.</h2>
        </div>
        <p>
          This is not the TBM production website and contains no claims about actual
          services or coverage. Those facts remain empty until TBM approves the knowledge
          base.
        </p>
      </section>

      <footer id="contact">
        <span>TBM chat pilot</span>
        <span>Standalone test environment</span>
      </footer>

      <Script
        src="/embed.js"
        strategy="afterInteractive"
        data-api-url={apiUrl}
        data-widget-url="/widget"
        data-locale="es"
        data-accent="#ff5a36"
      />
    </main>
  );
}
