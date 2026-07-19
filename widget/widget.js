/**
 * Support Brain — embeddable chat widget.
 *
 * Drop into any page with:
 *   <script src="widget.js" data-api="http://localhost:8000"></script>
 *
 * Config (in priority order):
 *   1. ?api=https://... query param on the host page (handy for ngrok demos)
 *   2. data-api attribute on this script tag
 *   3. default: http://localhost:8000
 *
 * Zero dependencies. Injects its own styles and DOM; nothing else on the
 * host page is touched.
 */
(function () {
  "use strict";

  var scriptEl = document.currentScript;
  var API_BASE =
    new URLSearchParams(location.search).get("api") ||
    (scriptEl && scriptEl.getAttribute("data-api")) ||
    "http://localhost:8000";
  API_BASE = API_BASE.replace(/\/+$/, "");

  var css = [
    ".sb-root{position:fixed;bottom:24px;right:24px;z-index:99999;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}",
    ".sb-bubble{width:56px;height:56px;border:none;border-radius:50%;background:#3d5af1;color:#fff;cursor:pointer;box-shadow:0 4px 14px rgba(20,30,80,.35);display:flex;align-items:center;justify-content:center;transition:transform .15s}",
    ".sb-bubble:hover{transform:scale(1.06)}",
    ".sb-bubble svg{width:26px;height:26px}",
    ".sb-panel{position:absolute;bottom:72px;right:0;width:min(370px,calc(100vw - 32px));height:min(540px,calc(100vh - 120px));background:#fff;border-radius:14px;box-shadow:0 8px 40px rgba(20,30,80,.28);display:none;flex-direction:column;overflow:hidden}",
    ".sb-panel.sb-open{display:flex}",
    ".sb-head{background:#3d5af1;color:#fff;padding:14px 16px;display:flex;align-items:center;gap:10px}",
    ".sb-head-dot{width:9px;height:9px;border-radius:50%;background:#5ee87c;flex:none}",
    ".sb-head-title{font-weight:600;font-size:15px}",
    ".sb-head-sub{font-size:11.5px;opacity:.85}",
    ".sb-close{margin-left:auto;background:none;border:none;color:#fff;font-size:20px;cursor:pointer;opacity:.85;padding:2px 6px}",
    ".sb-close:hover{opacity:1}",
    ".sb-log{flex:1;overflow-y:auto;padding:14px;background:#f4f6fb;display:flex;flex-direction:column;gap:10px}",
    ".sb-msg{max-width:85%;padding:9px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}",
    ".sb-msg-user{align-self:flex-end;background:#3d5af1;color:#fff;border-bottom-right-radius:4px}",
    ".sb-msg-bot{align-self:flex-start;background:#fff;color:#1d2433;border:1px solid #e3e7f0;border-bottom-left-radius:4px}",
    ".sb-msg-err{align-self:flex-start;background:#fdeaea;color:#8f2222;border:1px solid #f2c8c8}",
    ".sb-src{margin-top:8px;font-size:12px;color:#5a6478}",
    ".sb-src summary{cursor:pointer;color:#3d5af1;font-weight:600;outline:none}",
    ".sb-src ul{margin:6px 0 0;padding-left:16px}",
    ".sb-src li{margin-bottom:3px}",
    ".sb-typing{align-self:flex-start;background:#fff;border:1px solid #e3e7f0;border-radius:12px;padding:12px 14px;display:flex;gap:5px}",
    ".sb-typing i{width:7px;height:7px;border-radius:50%;background:#a9b3c9;animation:sb-blink 1.2s infinite}",
    ".sb-typing i:nth-child(2){animation-delay:.2s}",
    ".sb-typing i:nth-child(3){animation-delay:.4s}",
    "@keyframes sb-blink{0%,80%,100%{opacity:.3}40%{opacity:1}}",
    ".sb-form{display:flex;gap:8px;padding:12px;background:#fff;border-top:1px solid #e3e7f0}",
    ".sb-input{flex:1;border:1px solid #cdd4e3;border-radius:8px;padding:9px 11px;font:inherit;outline:none}",
    ".sb-input:focus{border-color:#3d5af1}",
    ".sb-send{border:none;border-radius:8px;background:#3d5af1;color:#fff;padding:0 16px;font:inherit;font-weight:600;cursor:pointer}",
    ".sb-send:disabled{background:#a9b3c9;cursor:default}",
  ].join("\n");

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var root = document.createElement("div");
  root.className = "sb-root";
  root.innerHTML =
    '<div class="sb-panel" role="dialog" aria-label="Support chat">' +
    '  <div class="sb-head">' +
    '    <span class="sb-head-dot"></span>' +
    "    <div><div class='sb-head-title'>Support</div><div class='sb-head-sub'>AI assistant &middot; answers from our official docs</div></div>" +
    '    <button class="sb-close" aria-label="Close chat">&times;</button>' +
    "  </div>" +
    '  <div class="sb-log"></div>' +
    '  <form class="sb-form">' +
    '    <input class="sb-input" type="text" placeholder="Ask about baggage, fees, refunds..." maxlength="500" autocomplete="off">' +
    '    <button class="sb-send" type="submit">Send</button>' +
    "  </form>" +
    "</div>" +
    '<button class="sb-bubble" aria-label="Open support chat">' +
    '  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' +
    "</button>";
  document.body.appendChild(root);

  var panel = root.querySelector(".sb-panel");
  var bubble = root.querySelector(".sb-bubble");
  var log = root.querySelector(".sb-log");
  var form = root.querySelector(".sb-form");
  var input = root.querySelector(".sb-input");
  var sendBtn = root.querySelector(".sb-send");
  var greeted = false;

  function togglePanel(open) {
    panel.classList.toggle("sb-open", open);
    if (open) {
      if (!greeted) {
        greeted = true;
        addBot(
          "Hi! I can answer questions about baggage allowances, fees, refunds and travel rules — straight from our official documents. What would you like to know?"
        );
      }
      input.focus();
    }
  }
  bubble.addEventListener("click", function () {
    togglePanel(!panel.classList.contains("sb-open"));
  });
  root.querySelector(".sb-close").addEventListener("click", function () {
    togglePanel(false);
  });

  function scrollLog() {
    log.scrollTop = log.scrollHeight;
  }

  function addMsg(cls, text) {
    var el = document.createElement("div");
    el.className = "sb-msg " + cls;
    el.textContent = text;
    log.appendChild(el);
    scrollLog();
    return el;
  }
  function addBot(text) {
    return addMsg("sb-msg-bot", text);
  }

  function addSources(msgEl, sources) {
    if (!sources || !sources.length) return;
    var det = document.createElement("details");
    det.className = "sb-src";
    var sum = document.createElement("summary");
    sum.textContent =
      sources.length + " source" + (sources.length > 1 ? "s" : "");
    det.appendChild(sum);
    var ul = document.createElement("ul");
    sources.forEach(function (s) {
      var li = document.createElement("li");
      var loc = s.location ? " — " + s.location : "";
      li.textContent = s.source + loc;
      ul.appendChild(li);
    });
    det.appendChild(ul);
    msgEl.appendChild(det);
    scrollLog();
  }

  var typingEl = null;
  function showTyping(on) {
    if (on && !typingEl) {
      typingEl = document.createElement("div");
      typingEl.className = "sb-typing";
      typingEl.innerHTML = "<i></i><i></i><i></i>";
      log.appendChild(typingEl);
      scrollLog();
    } else if (!on && typingEl) {
      typingEl.remove();
      typingEl = null;
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (q.length < 3 || sendBtn.disabled) return;
    addMsg("sb-msg-user", q);
    input.value = "";
    sendBtn.disabled = true;
    showTyping(true);

    fetch(API_BASE + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("API returned " + res.status);
        return res.json();
      })
      .then(function (data) {
        showTyping(false);
        var el = addBot(data.answer);
        addSources(el, data.sources);
      })
      .catch(function (err) {
        showTyping(false);
        addMsg(
          "sb-msg sb-msg-err",
          "Sorry, I couldn't reach the assistant (" +
            err.message +
            "). Is the backend running?"
        );
      })
      .finally(function () {
        sendBtn.disabled = false;
        input.focus();
      });
  });
})();
