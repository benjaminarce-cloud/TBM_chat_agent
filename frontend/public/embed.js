(function () {
  "use strict";

  var script = document.currentScript;
  if (!script || window.__tbmChatLoaded) return;
  window.__tbmChatLoaded = true;
  script.dataset.tbmLoaded = "true";

  var scriptOrigin = new URL(script.src, window.location.href).origin;
  var apiUrl = script.dataset.apiUrl || "http://localhost:8000";
  var widgetUrl = new URL(script.dataset.widgetUrl || "/widget", scriptOrigin);
  var locale = script.dataset.locale === "en" ? "en" : "es";
  var accent = script.dataset.accent || "#ff5a36";
  var pageUrl = new URL(window.location.href);

  widgetUrl.searchParams.set("apiUrl", apiUrl);
  widgetUrl.searchParams.set("parentOrigin", window.location.origin);
  widgetUrl.searchParams.set("parentPage", pageUrl.toString());
  widgetUrl.searchParams.set("referrer", document.referrer || "");
  ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"].forEach(
    function (key) {
      var value = pageUrl.searchParams.get(key);
      if (value) widgetUrl.searchParams.set(key, value);
    },
  );
  widgetUrl.searchParams.set("locale", locale);

  var frame = document.createElement("iframe");
  frame.src = widgetUrl.toString();
  frame.title = locale === "en" ? "Chat with TBM Carriers" : "Chatea con TBM Carriers";
  frame.setAttribute("allow", "clipboard-write");
  frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms");
  frame.referrerPolicy = "no-referrer";
  frame.style.cssText = [
    "position:fixed",
    "right:22px",
    "bottom:94px",
    "width:min(390px,calc(100vw - 28px))",
    "height:min(650px,calc(100dvh - 118px))",
    "border:0",
    "border-radius:18px",
    "box-shadow:0 24px 80px rgba(9,31,34,.24),0 6px 18px rgba(9,31,34,.12)",
    "background:#fff",
    "z-index:2147483646",
    "opacity:0",
    "transform:translateY(14px) scale(.98)",
    "transform-origin:bottom right",
    "pointer-events:none",
    "transition:opacity .18s ease,transform .18s ease",
  ].join(";");

  var button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", locale === "en" ? "Open TBM chat" : "Abrir chat de TBM");
  button.setAttribute("aria-expanded", "false");
  button.textContent = locale === "en" ? "Chat  ↗" : "Chat  ↗";
  button.style.cssText = [
    "position:fixed",
    "right:22px",
    "bottom:22px",
    "height:56px",
    "padding:0 20px",
    "border:0",
    "border-radius:16px",
    "color:#fff",
    "background:" + accent,
    "box-shadow:0 10px 30px rgba(13,35,38,.22)",
    "font:800 14px/1 Arial,sans-serif",
    "letter-spacing:.01em",
    "cursor:pointer",
    "z-index:2147483647",
  ].join(";");

  var open = false;
  function setOpen(nextOpen) {
    open = nextOpen;
    button.setAttribute("aria-expanded", String(open));
    button.setAttribute(
      "aria-label",
      open
        ? locale === "en"
          ? "Close TBM chat"
          : "Cerrar chat de TBM"
        : locale === "en"
          ? "Open TBM chat"
          : "Abrir chat de TBM",
    );
    button.textContent = open ? "Close  ×" : "Chat  ↗";
    frame.style.opacity = open ? "1" : "0";
    frame.style.transform = open ? "translateY(0) scale(1)" : "translateY(14px) scale(.98)";
    frame.style.pointerEvents = open ? "auto" : "none";
    if (open) frame.focus();
  }
  button.addEventListener("click", function () {
    setOpen(!open);
  });
  document.querySelectorAll("[data-tbm-chat-open]").forEach(function (trigger) {
    trigger.addEventListener("click", function () {
      setOpen(true);
    });
  });

  var media = window.matchMedia("(max-width: 560px)");
  function sizeForMobile(event) {
    if (event.matches) {
      frame.style.right = "8px";
      frame.style.bottom = "82px";
      frame.style.width = "calc(100vw - 16px)";
      frame.style.height = "calc(100dvh - 94px)";
      frame.style.borderRadius = "16px";
      button.style.right = "14px";
      button.style.bottom = "14px";
    } else {
      frame.style.right = "22px";
      frame.style.bottom = "94px";
      frame.style.width = "min(390px,calc(100vw - 28px))";
      frame.style.height = "min(650px,calc(100dvh - 118px))";
      frame.style.borderRadius = "18px";
      button.style.right = "22px";
      button.style.bottom = "22px";
    }
  }
  sizeForMobile(media);
  media.addEventListener("change", sizeForMobile);

  document.body.appendChild(frame);
  document.body.appendChild(button);
})();
