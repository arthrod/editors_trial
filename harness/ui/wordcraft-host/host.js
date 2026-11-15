/**
 * Loader shim for the WordCraft browser perf host (port 5219).
 *
 * WordCraft's web app (apps/wordcraft-web, Trunk + eframe/egui) has no query param or route that
 * opens a file: File > Open uses the browser picker (rfd) and a dropped file goes through the same
 * inbox (`apps/wordcraft-web/src/web.rs` -> `wordcraft_ui_egui::Inbox` -> `file.open`). This shim
 * fetches `/corpus.docx` and dispatches a real `drop` on the app's canvas, so the document enters
 * through the app's own open-document path.
 *
 * Ready signal: the app draws into one <canvas> and publishes no DOM/JS state, but it keeps its
 * window title in sync with the open document (`crates/ui-egui/src/app/frame.rs::sync_title_and_frame`,
 * at the end of every frame) and eframe's web runner logs the title it cannot apply:
 *
 *   [eframe::web::app_runner] eframe/src/web/app_runner.rs:353:
 *   Unhandled egui viewport command: Title("corpus - WordCraft") - not implemented in web backend
 *
 * So a title frame naming the opened document is the app's own statement that the document is now
 * the session's document, issued at the end of the frame that laid it out and painted it. Readiness
 * waits for that line (console.warn is tapped, and still forwarded), then for two animation frames,
 * so the paint of that frame has been presented before the driver clicks and types.
 *
 * Contract with perf/runner/warm_cold_browser.mjs:
 *   window.__WORDCRAFT_READY__ === true          <-- ready_js
 *   #wc-ready[data-state="rendered"]             <-- ready_selector
 *   window.__WORDCRAFT_HOST__                    <-- diagnostics (state, titles, errors)
 *
 * Content oracle: the Trunk/WASM app exposes no JS API for session plain text
 * (plain_text lives in Rust only). There is no __PERF_MODEL_TEXT__; C03/C11
 * refuse canvas samples as document_content_unverifiable rather than timing
 * unverified loads.
 */
(() => {
  const config = window.__WORDCRAFT_HOST_CFG__ || {};
  const corpusRoute = config.corpusRoute || "/corpus.docx";
  const docName = config.docName || "corpus.docx";
  // The title line names the document without its extension (`corpus - WordCraft`).
  const docStem = docName.replace(/\.[^.]+$/, "").toLowerCase();
  const DOCX_MIME =
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

  const host = (window.__WORDCRAFT_HOST__ = {
    state: "booting",
    t0: performance.now(),
    readyAt: null,
    readyMs: null,
    openedBytes: 0,
    openSentAt: null,
    titles: [],
    titleFrame: null,
    errors: [],
    scrollForwards: 0,
    lastScrollDelta: 0,
  });

  // ---------------------------------------------------------------- console tap (before the app)
  // Trunk's module script is deferred and this is a classic script, so this runs first. Every line is
  // still printed: the tap must never hide the app's own console evidence.
  const TITLE_RE = /Title\("([^"]*)"\)/;
  for (const level of ["warn", "log", "info"]) {
    const original = console[level].bind(console);
    console[level] = (...args) => {
      try {
        const line = args.map((a) => (typeof a === "string" ? a : String(a))).join(" ");
        const m = TITLE_RE.exec(line);
        if (m) {
          host.titles.push({ t: Math.round(performance.now() - host.t0), title: m[1] });
        }
      } catch {
        /* never let the tap break the app */
      }
      original(...args);
    };
  }

  const chip = document.createElement("div");
  chip.id = "wc-ready";
  chip.dataset.state = "booting";
  chip.setAttribute("aria-hidden", "true");
  chip.textContent = "wordcraft-host: booting";
  Object.assign(chip.style, {
    position: "fixed",
    left: "8px",
    bottom: "8px",
    zIndex: "2147483647",
    font: "10px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace",
    padding: "2px 6px",
    border: "1px solid rgba(0,0,0,.25)",
    borderRadius: "4px",
    background: "rgba(255,255,255,.82)",
    color: "#3f3f46",
    pointerEvents: "none",
    whiteSpace: "nowrap",
  });

  function setState(state, detail) {
    host.state = state;
    chip.dataset.state = state;
    chip.textContent = `wordcraft-host: ${state}${detail ? ` ${detail}` : ""}`;
  }

  const mountChip = () => {
    if (!chip.isConnected && document.body) document.body.appendChild(chip);
  };
  if (document.body) mountChip();
  else document.addEventListener("DOMContentLoaded", mountChip, { once: true });

  window.addEventListener("error", (e) => host.errors.push(`window.error: ${e.message}`));
  window.addEventListener("unhandledrejection", (e) =>
    host.errors.push(`unhandledrejection: ${(e.reason && e.reason.message) || e.reason}`),
  );

  const canvas = () => document.getElementById("wordcraft_canvas");
  const nextFrames = (n) =>
    new Promise((resolve) => {
      let left = n;
      const step = () => (left-- > 0 ? requestAnimationFrame(step) : resolve());
      requestAnimationFrame(step);
    });

  // ---------------------------------------------------------------- scroll surface (C10)
  // perf/runner/adversarial_c10_scroll.mjs sets `scrollTop` on the largest `overflow-y: auto|scroll`
  // element with `scrollHeight - clientHeight >= 200`. A canvas app has none, and with none the probe
  // would time two empty animation frames. This overlay is that element: its scroll is forwarded to
  // the canvas as a `wheel` event of the same pixel delta (eframe listens for `wheel` on the canvas),
  // a jump of about one viewport, like a DOM editor's half-document jump.
  function installScrollSurface() {
    const el = document.createElement("div");
    el.id = "wc-scroll";
    const spacer = document.createElement("div");
    Object.assign(el.style, {
      position: "fixed",
      inset: "0",
      overflowY: "scroll",
      overflowX: "hidden",
      zIndex: "2147483600",
      opacity: "0",
      pointerEvents: "none",
    });
    spacer.style.width = "1px";
    const size = () => {
      spacer.style.height = `${Math.max(3 * window.innerHeight, 1200)}px`;
    };
    size();
    el.appendChild(spacer);
    document.body.appendChild(el);
    let last = 0;
    el.addEventListener(
      "scroll",
      () => {
        const delta = el.scrollTop - last;
        last = el.scrollTop;
        const c = canvas();
        if (!delta || !c) return;
        const r = c.getBoundingClientRect();
        c.dispatchEvent(
          new WheelEvent("wheel", {
            deltaY: delta,
            deltaMode: 0,
            bubbles: true,
            cancelable: true,
            clientX: r.left + r.width / 2,
            clientY: r.top + r.height / 2,
          }),
        );
        host.scrollForwards += 1;
        host.lastScrollDelta = Math.round(delta);
      },
      { passive: true },
    );
    window.addEventListener("resize", size);
  }
  installScrollSurface();

  // ---------------------------------------------------------------- open the document
  async function dispatchDrop(bytes) {
    const c = canvas();
    if (!c) throw new Error("no #wordcraft_canvas");
    const dt = new DataTransfer();
    dt.items.add(new File([bytes], docName, { type: DOCX_MIME }));
    // dragover first: eframe's handler previews hovered files and the drop clears that list.
    for (const type of ["dragenter", "dragover"]) {
      c.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer: dt }));
    }
    await nextFrames(1);
    c.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
  }

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function run() {
    const bytesPromise = fetch(corpusRoute, { cache: "no-store" }).then((r) => {
      if (!r.ok) throw new Error(`GET ${corpusRoute} -> ${r.status}`);
      return r.arrayBuffer();
    });
    bytesPromise.catch((e) => {
      host.errors.push(String(e));
      setState("failed", "corpus");
    });

    // The runner is up once Trunk's loading overlay is gone (removed after `WebRunner::start`).
    const bootDeadline = performance.now() + 120_000;
    let booted = false;
    while (performance.now() < bootDeadline) {
      const c = canvas();
      const loading = document.getElementById("wordcraft_loading");
      if (loading && /failed to start/i.test(loading.textContent || "")) {
        host.errors.push(`app failed to start: ${loading.textContent}`);
        setState("failed", "app");
        return;
      }
      if (c && c.width > 0 && c.height > 0 && !loading) {
        booted = true;
        break;
      }
      await sleep(30);
    }
    if (!booted) {
      setState("failed", "app never booted");
      return;
    }

    const bytes = await bytesPromise;
    host.openedBytes = bytes.byteLength;
    host.openSentAt = Math.round(performance.now() - host.t0);
    setState("opening", `${bytes.byteLength}B`);
    await dispatchDrop(bytes);

    // Wait for the app's title frame naming this document. A title seen before the drop (the blank
    // app's own `Title("WordCraft")`) never counts, and the opened document's title carries the stem.
    const preOpen = new Set(
      host.titles.filter((entry) => entry.t < host.openSentAt).map((entry) => entry.title),
    );
    const deadline = performance.now() + 90_000;
    while (performance.now() < deadline) {
      const titled = host.titles.find(
        (entry) =>
          entry.t >= host.openSentAt &&
          !preOpen.has(entry.title) &&
          entry.title.toLowerCase().includes(docStem),
      );
      if (titled) {
        host.titleFrame = titled;
        await nextFrames(2);
        host.readyAt = performance.now();
        host.readyMs = Math.round(host.readyAt - host.t0);
        window.__WORDCRAFT_READY__ = true;
        setState("rendered", `${host.readyMs}ms`);
        return;
      }
      await sleep(30);
    }
    setState("failed", "document never opened");
  }

  run().catch((e) => {
    host.errors.push(String((e && e.stack) || e));
    setState("failed", String(e && e.message ? e.message : e));
  });
})();
