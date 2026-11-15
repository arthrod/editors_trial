/**
 * Host app for the Office-Open rendering study.
 *
 * Office-Open (https://github.com/DemoMacro/office-open) is a headless
 * TypeScript library: it generates, parses and patches OOXML. It ships no
 * visual editor/viewer of its own -- its only web app is the Nuxt docs site,
 * whose assistant is generate-only and cannot ingest a .docx. The brief
 * therefore allows a host app under harness/ui/<slug>/ that imports the
 * editor's package from the repo (repos/ stays read-only).
 *
 * This app imports the repo's own build of @office-open/docx and calls its
 * public parseDocument() on the corpus. Everything drawn below is derived
 * *only* from that parsed model -- no knowledge of the fixture is baked in.
 * Office-Open provides no layout engine, so the app lays the model out in a
 * continuous flow (one sheet per w:sectPr) and says so on screen.
 */
import { parseDocument } from "@office-open/docx";

const TWIP = 1 / 15; // twips -> px @96dpi
const EMU = 1 / 9525; // EMU   -> px @96dpi
const PT = 4 / 3; // points -> px @96dpi

const census = {};
const bump = (k, n = 1) => (census[k] = (census[k] || 0) + n);

const el = (tag, cls, txt) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined && txt !== null) e.textContent = String(txt);
  return e;
};

function toBytes(v) {
  if (!v) return null;
  if (v instanceof Uint8Array) return v;
  if (ArrayBuffer.isView(v)) return new Uint8Array(v.buffer, v.byteOffset, v.byteLength);
  if (v instanceof ArrayBuffer) return new Uint8Array(v);
  if (Array.isArray(v)) return new Uint8Array(v);
  if (v && Array.isArray(v.data)) return new Uint8Array(v.data);
  return null;
}

function toDataUrl(bytes, mime = "image/png") {
  const u8 = toBytes(bytes);
  if (!u8 || !u8.length) return null;
  let bin = "";
  const CH = 0x8000;
  for (let i = 0; i < u8.length; i += CH) {
    bin += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
  }
  return `data:${mime};base64,${btoa(bin)}`;
}

// --------------------------------------------------------------------------
// run formatting
// --------------------------------------------------------------------------
function runStyle(node) {
  const st = {};
  const f = node.font || {};
  const fam = f.ascii || f.hAnsi;
  if (fam) st.fontFamily = `"${fam}", Calibri, "Segoe UI", sans-serif`;
  if (node.bold) st.fontWeight = "700";
  if (node.italic) st.fontStyle = "italic";
  if (node.underline) st.textDecoration = "underline";
  if (node.strike || node.doubleStrike) {
    st.textDecoration = `${st.textDecoration ? st.textDecoration + " " : ""}line-through`;
  }
  if (node.color && node.color !== "auto") st.color = `#${String(node.color).replace(/^#/, "")}`;
  if (node.size) st.fontSize = `${(Number(node.size) * 0.5 * PT).toFixed(2)}px`;
  if (node.allCaps) st.textTransform = "uppercase";
  if (node.smallCaps) st.fontVariant = "small-caps";
  if (node.vanish) {
    // Word hides vanish runs unless "hidden text" display is on.
    st.display = "none";
    bump("vanish");
  }
  if (node.noProof) bump("noProof");
  if (node.verticalAlign === "superscript" || node.verticalAlign === "subscript") {
    st.verticalAlign = node.verticalAlign;
    st.fontSize = "0.72em";
    bump("verticalAlign");
  }
  if (node.highlight) st.backgroundColor = `#${String(node.highlight).replace(/^#/, "")}`;
  if (node.shading?.fill && node.shading.fill !== "auto") {
    st.backgroundColor = `#${String(node.shading.fill).replace(/^#/, "")}`;
  }
  if (node.characterSpacing) st.letterSpacing = `${Number(node.characterSpacing) / 20}px`;
  if (node.textOutline) {
    const rgb = node.textOutline.fill?.solid?.srgb?.val;
    const w = node.textOutline.width ? Number(node.textOutline.width) * EMU : 1;
    st.WebkitTextStroke = `${Math.max(w, 0.6)}px #${rgb || "000000"}`;
    st.paintOrder = "stroke fill";
  }
  return st;
}

function applyStyle(e, st) {
  for (const [k, v] of Object.entries(st)) {
    if (k === "WebkitTextStroke") e.style.webkitTextStroke = v;
    else e.style[k] = v;
  }
  return e;
}

// --------------------------------------------------------------------------
// charts (generic projection of the model's chart data)
// --------------------------------------------------------------------------
function renderChart(chart) {
  const wrap = el("div", "obj chart");
  const w = Math.round((chart.transformation?.width || 5486400) * EMU);
  const h = Math.round((chart.transformation?.height || 3200400) * EMU);
  const series = chart.series || [];
  const cats =
    chart.categories ||
    series[0]?.categorySource?.categories ||
    series[0]?.categories ||
    [];
  const valuesOf = (s) => s.values || s.points?.map((p) => p.value) || [];
  const isBar = chart.type === "bar";
  const rawMax = Math.max(
    0,
    ...series.flatMap((s) => valuesOf(s).map((v) => Math.abs(Number(v) || 0)))
  );
  // nice axis steps (1 / 2 / 2.5 / 5 x 10^k) anchored at 0, like Word
  const rough = rawMax / 5 || 1;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
  const maxV = Math.max(step, Math.ceil(rawMax / step) * step);
  const SVG = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const padL = 44;
  const padB = 28;
  const padT = 10;
  const padR = chart.showLegend ? 110 : 10;

  const mk = (tag, attrs, text) => {
    const n = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  };
  // value axis + gridlines
  const ticks = Math.round(maxV / step);
  for (let i = 0; i <= ticks; i++) {
    const val = step * i;
    const frac = isBar ? (maxV - val) / maxV : val / maxV;
    const y = padT + (h - padT - padB) * (isBar ? frac : 1 - frac);
    const x = isBar ? padL : padL;
    const yy = isBar ? y : y;
    svg.appendChild(
      mk("line", {
        x1: padL,
        y1: yy,
        x2: w - padR,
        y2: yy,
        stroke: "#d9d9d9",
        "stroke-width": 1,
      })
    );
    const lbl = mk(
      "text",
      { x: padL - 6, y: yy + 4, "text-anchor": "end", "font-size": 10, fill: "#444" },
      String(Math.round(val * 100) / 100)
    );
    svg.appendChild(lbl);
  }
  // bars
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const nCats = Math.max(cats.length, 1);
  const groupW = plotW / nCats;
  series.forEach((s, si) => {
    const vals = valuesOf(s);
    const barW = (groupW * 0.6) / Math.max(series.length, 1);
    vals.forEach((v, ci) => {
      const vv = Math.abs(Number(v) || 0);
      const len = (vv / maxV) * (isBar ? plotW : plotH);
      const off = groupW * ci + groupW * 0.2 + si * barW;
      const color = ["#4472c4", "#ed7d31", "#a5a5a5", "#ffc000"][si % 4];
      if (isBar) {
        svg.appendChild(
          mk("rect", {
            x: padL + off,
            y: padT + plotH - len,
            width: barW,
            height: len,
            fill: color,
          })
        );
      } else {
        svg.appendChild(
          mk("rect", {
            x: padL + off,
            y: padT + plotH - len,
            width: barW,
            height: len,
            fill: color,
          })
        );
      }
    });
  });
  // category axis labels
  cats.forEach((c, ci) => {
    const x = padL + groupW * ci + groupW / 2;
    svg.appendChild(
      mk(
        "text",
        { x, y: h - padB + 16, "text-anchor": "middle", "font-size": 11, fill: "#333" },
        c
      )
    );
  });
  // axis lines
  svg.appendChild(
    mk("line", { x1: padL, y1: padT, x2: padL, y2: h - padB, stroke: "#888", "stroke-width": 1 })
  );
  svg.appendChild(
    mk("line", {
      x1: padL,
      y1: h - padB,
      x2: w - padR,
      y2: h - padB,
      stroke: "#888",
      "stroke-width": 1,
    })
  );
  // legend
  if (chart.showLegend) {
    series.forEach((s, si) => {
      const y = padT + 10 + si * 18;
      const color = ["#4472c4", "#ed7d31", "#a5a5a5", "#ffc000"][si % 4];
      svg.appendChild(mk("rect", { x: w - padR + 8, y: y - 8, width: 10, height: 10, fill: color }));
      svg.appendChild(
        mk(
          "text",
          { x: w - padR + 22, y: y, "font-size": 11, fill: "#333" },
          s.name || `Series ${si + 1}`
        )
      );
    });
  }
  wrap.appendChild(svg);
  return wrap;
}

// --------------------------------------------------------------------------
// generic node renderer
// --------------------------------------------------------------------------
const CONTENT_KEYS = [
  "picture", "chart", "smartArt", "object", "wpsShape", "math",
  "insertion", "deletion", "movedFrom", "movedTo",
  "footnoteReference", "endnoteReference", "commentReference",
  "pageBreak", "columnBreak", "tab", "noBreakHyphen", "softHyphen",
  "symbolRun", "simpleField", "complexField",
  "bookmarkStart", "bookmarkEnd",
  "commentRangeStart", "commentRangeEnd",
  "permStart", "permEnd",
  "moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
  "proofErr", "sdt", "altChunk", "table", "paragraph",
];

function renderNode(node, ctx) {
  const frag = document.createDocumentFragment();
  if (node === null || node === undefined) return frag;

  // a run-ish object: formatting + content
  const hasContent =
    CONTENT_KEYS.some((k) => k in node) ||
    "text" in node ||
    "deletedText" in node ||
    "children" in node;
  if (!hasContent) return frag;

  const st = runStyle(node);
  const span = el("span", "run");
  applyStyle(span, st);
  if (node.rightToLeft) span.dir = "rtl";
  if (node.style) span.classList.add(`rstyle-${node.style}`);

  let produced = false;

  for (const key of CONTENT_KEYS) {
    if (!(key in node)) continue;
    const v = node[key];
    switch (key) {
      case "picture": {
        bump("picture");
        const src = toDataUrl(v.data, `image/${v.type || "png"}`);
        const w = Math.round((v.transformation?.width || 0) * EMU);
        const h = Math.round((v.transformation?.height || 0) * EMU);
        const img = el("img", "picture");
        if (src) img.src = src;
        else img.alt = "(no image data)";
        if (w) img.style.width = `${w}px`;
        if (h) img.style.height = `${h}px`;
        const box = el("div", "obj");
        box.appendChild(img);
        if (v.altText?.description) box.appendChild(el("div", "obj-cap", `picture: ${v.altText.description}`));
        span.appendChild(box);
        produced = true;
        break;
      }
      case "chart": {
        bump("chart");
        const box = el("div", "obj");
        box.appendChild(renderChart(v));
        box.appendChild(
          el("div", "obj-cap", `chart: ${v.type}, ${v.series?.length || 0} series, ${(v.categories || []).length} categories`)
        );
        span.appendChild(box);
        produced = true;
        break;
      }
      case "smartArt": {
        bump("smartArt");
        const box = el("div", "obj smartart-band");
        const w = Math.round((v.transformation?.width || 0) * EMU);
        const h = Math.round((v.transformation?.height || 0) * EMU);
        box.style.width = `${w || 480}px`;
        box.style.height = `${h || 120}px`;
        const n = v.nodes?.length || 0;
        box.appendChild(
          el(
            "div",
            "obj-cap",
            n
              ? `SmartArt (${n} nodes)`
              : `SmartArt: shape list empty (layout ${String(v.layout?.uniqueId || "").split("/").pop()})`
          )
        );
        span.appendChild(box);
        produced = true;
        break;
      }
      case "object": {
        bump("object");
        const box = el("div", "obj ole");
        const src = toDataUrl(v.iconImage?.data, `image/${v.iconImage?.type || "png"}`);
        const w = Math.round(parseFloat(v.width || "108pt") * PT);
        const h = Math.round(parseFloat(v.height || "72pt") * PT);
        const img = el("img", "ole-icon");
        if (src) img.src = src;
        else img.alt = "(no OLE preview image)";
        img.style.width = `${w}px`;
        img.style.height = `${h}px`;
        box.appendChild(img);
        box.appendChild(
          el("div", "obj-cap", `OLE object: ${v.embed?.progId || "?"} (${v.embed?.fileName || "?"})`)
        );
        span.appendChild(box);
        produced = true;
        break;
      }
      case "wpsShape": {
        bump("wpsShape");
        const box = el("div", "obj textbox");
        const w = Math.round((v.transformation?.width || 0) * EMU);
        const h = Math.round((v.transformation?.height || 0) * EMU);
        if (w) box.style.width = `${w}px`;
        if (h) box.style.height = `${h}px`;
        const inner = el("div", "textbox-inner");
        (v.children || []).forEach((c) => inner.appendChild(renderNode(c, ctx)));
        box.appendChild(inner);
        if (v.vmlFallback) {
          const m = v.vmlFallback.match(/<w:t>([^<]*)<\/w:t>/);
          box.appendChild(el("div", "obj-cap", `mc:Fallback vmlFallback text: "${m ? m[1] : "?"}"`));
        }
        span.appendChild(box);
        produced = true;
        break;
      }
      case "math": {
        bump("math");
        const box = el("div", "obj math");
        (v.equations || []).forEach((eq) => {
          eq.forEach((part) => {
            const s = el("span", "math-part", part.text || "");
            const fam = part.runProperties?.font?.ascii;
            if (fam) s.style.fontFamily = `"${fam}", "Cambria Math", serif`;
            box.appendChild(s);
          });
        });
        span.appendChild(box);
        produced = true;
        break;
      }
      case "insertion": {
        bump("insertion");
        const s = el("span", "rev ins", "");
        (v.children || []).forEach((c) => s.appendChild(renderNode(c, ctx)));
        s.title = `inserted by ${v.author}`;
        span.appendChild(s);
        produced = true;
        break;
      }
      case "deletion": {
        bump("deletion");
        const s = el("span", "rev del", "");
        (v.children || []).forEach((c) => s.appendChild(renderNode(c, ctx)));
        s.title = `deleted by ${v.author}`;
        span.appendChild(s);
        produced = true;
        break;
      }
      case "movedFrom": {
        bump("movedFrom");
        const s = el("span", "rev movfrom", "");
        (v.children || []).forEach((c) => s.appendChild(renderNode(c, ctx)));
        span.appendChild(s);
        produced = true;
        break;
      }
      case "movedTo": {
        bump("movedTo");
        const s = el("span", "rev moveto", "");
        (v.children || []).forEach((c) => s.appendChild(renderNode(c, ctx)));
        span.appendChild(s);
        produced = true;
        break;
      }
      case "footnoteReference": {
        bump("footnoteReference");
        const n = ctx.footnoteNumber(v);
        const sup = el("sup", "note-ref", String(n));
        sup.dataset.commentId = String(v);
        span.appendChild(sup);
        produced = true;
        break;
      }
      case "endnoteReference": {
        bump("endnoteReference");
        const n = ctx.endnoteNumber(v);
        span.appendChild(el("sup", "note-ref", String(n)));
        produced = true;
        break;
      }
      case "commentReference": {
        bump("commentReference");
        const sup = el("sup", "comment-ref", "◆");
        sup.dataset.commentId = String(v);
        sup.title = "comment reference";
        span.appendChild(sup);
        produced = true;
        break;
      }
      case "pageBreak": {
        bump("pageBreak");
        span.appendChild(el("span", "break-mark", "page break"));
        produced = true;
        break;
      }
      case "columnBreak": {
        bump("columnBreak");
        span.appendChild(el("span", "break-mark", "column break"));
        produced = true;
        break;
      }
      case "tab": {
        span.appendChild(el("span", "tab"));
        produced = true;
        break;
      }
      case "noBreakHyphen": {
        span.appendChild(document.createTextNode("‑"));
        produced = true;
        break;
      }
      case "softHyphen": {
        span.appendChild(el("span", "soft-hyphen", "­"));
        produced = true;
        break;
      }
      case "symbolRun": {
        const s = el("span", "symbol", v.char ?? "");
        if (v.symbolFont) s.style.fontFamily = `"${v.symbolFont}", "Segoe UI Symbol", serif`;
        span.appendChild(s);
        produced = true;
        break;
      }
      case "simpleField":
      case "complexField": {
        const val = v.cachedValue ?? v.result ?? "";
        span.appendChild(el("span", "field", val));
        produced = true;
        break;
      }
      case "bookmarkStart": {
        span.appendChild(el("span", "mark bookmark", "⚑"));
        span.appendChild(document.createTextNode(""));
        produced = true;
        break;
      }
      case "bookmarkEnd":
      case "proofErr":
      case "commentRangeStart":
      case "commentRangeEnd":
      case "permStart":
      case "permEnd":
      case "moveFromRangeStart":
      case "moveFromRangeEnd":
      case "moveToRangeStart":
      case "moveToRangeEnd": {
        bump(key);
        produced = true;
        break;
      }
      case "sdt": {
        bump("sdt");
        span.appendChild(renderSdt(v, ctx));
        produced = true;
        break;
      }
      case "altChunk": {
        bump("altChunk");
        span.appendChild(renderAltChunk(v));
        produced = true;
        break;
      }
      case "table": {
        bump("table");
        span.appendChild(renderTable(v, ctx));
        produced = true;
        break;
      }
      case "paragraph": {
        span.appendChild(renderParagraph(v, ctx));
        produced = true;
        break;
      }
    }
  }

  if ("text" in node && node.text !== undefined && node.text !== null) {
    span.appendChild(document.createTextNode(String(node.text)));
    produced = true;
  }
  if ("deletedText" in node && node.deletedText !== undefined) {
    span.appendChild(document.createTextNode(String(node.deletedText)));
    produced = true;
  }
  if (Array.isArray(node.children)) {
    node.children.forEach((c) => span.appendChild(renderNode(c, ctx)));
    produced = true;
  }
  if (node.revision) {
    bump("revision");
    span.classList.add("format-revision");
    span.title = `formatting changed by ${node.revision.author}`;
  }
  if (!produced) return frag;
  return span;
}

function renderSdt(sdt, ctx) {
  const box = el("div", "sdt");
  const p = sdt.properties || {};
  const alias = p.alias || p.tag || `id ${p.id ?? "?"}`;
  box.appendChild(el("div", "sdt-tag", `content control: ${alias}`));
  const body = el("div", "sdt-body");
  (sdt.children || []).forEach((c) => body.appendChild(renderNode(c, ctx)));
  box.appendChild(body);
  return box;
}

function renderAltChunk(chunk) {
  const box = el("div", "altchunk");
  const bytes = toBytes(chunk.data);
  let html = "";
  if (bytes) html = new TextDecoder("utf-8").decode(bytes);
  box.appendChild(el("div", "obj-cap", `altChunk (${chunk.contentType || "?"}) imported as HTML:`));
  const body = el("div", "altchunk-body");
  if (html) body.innerHTML = html;
  else body.textContent = "(no altChunk payload)";
  box.appendChild(body);
  return box;
}

function renderTable(tbl, ctx) {
  const wrap = el("div", "tbl-wrap");
  const t = el("table", "doc-table");
  if (tbl.style) t.dataset.style = tbl.style;
  if (tbl.alignment) t.style.marginLeft = tbl.alignment === "center" ? "auto" : "0";
  if (tbl.alignment === "center") t.style.marginRight = "auto";
  (tbl.rows || []).forEach((row) => {
    const tr = el("tr");
    if (row.tableHeader) tr.classList.add("tbl-header");
    (row.cells || []).forEach((cell) => {
      const tc = el(row.tableHeader ? "th" : "td");
      if (cell.width?.size) tc.style.width = `${Math.round(cell.width.size * TWIP)}px`;
      if (cell.columnSpan > 1) tc.colSpan = cell.columnSpan;
      if (cell.shading?.fill && cell.shading.fill !== "auto") {
        tc.style.backgroundColor = `#${cell.shading.fill}`;
      }
      if (cell.verticalAlign) tc.style.verticalAlign = cell.verticalAlign;
      (cell.children || []).forEach((c) => tc.appendChild(renderNode(c, ctx)));
      tr.appendChild(tc);
    });
    t.appendChild(tr);
  });
  wrap.appendChild(t);
  return wrap;
}

function renderParagraph(p, ctx) {
  const para = el("p", "para");
  const styleId = p.heading || p.style;
  if (p.heading) para.classList.add("heading");
  if (styleId) para.dataset.style = styleId;
  if (p.alignment) para.style.textAlign = p.alignment;
  if (p.indent?.left) para.style.marginLeft = `${Math.round(p.indent.left * TWIP)}px`;
  if (p.spacing?.before) para.style.marginTop = `${Math.round(p.spacing.before * TWIP)}px`;
  if (p.spacing?.after) para.style.marginBottom = `${Math.round(p.spacing.after * TWIP)}px`;
  if (p.revision) {
    bump("paragraphRevision");
    para.classList.add("has-revision");
    para.title = `paragraph mark changed by ${p.revision.author}`;
  }
  if (p.run) {
    // paragraph-mark run properties (w:pPr/w:rPr)
    const mark = el("span", "pmark");
    applyStyle(mark, runStyle(p.run));
    para.appendChild(mark);
  }
  if (typeof p.text === "string") para.appendChild(document.createTextNode(p.text));
  (p.children || []).forEach((c) => para.appendChild(renderNode(c, ctx)));
  return para;
}

// --------------------------------------------------------------------------
// document rendering
// --------------------------------------------------------------------------
function renderDocument(doc) {
  const root = el("div", "doc");
  const ctx = {
    fnNums: new Map(),
    enNums: new Map(),
    footnotes: new Map(),
    endnotes: new Map(),
    comments: new Map(),
    footnoteNumber(id) {
      if (!this.fnNums.has(id)) this.fnNums.set(id, this.fnNums.size + 1);
      return this.fnNums.get(id);
    },
    endnoteNumber(id) {
      if (!this.enNums.has(id)) this.enNums.set(id, this.enNums.size + 1);
      return this.enNums.get(id);
    },
  };
  (doc.footnotes || []).forEach((f) => ctx.footnotes.set(f.id, f));
  (doc.endnotes || []).forEach((f) => ctx.endnotes.set(f.id, f));
  (doc.comments || []).forEach((c) => ctx.comments.set(c.id, c));

  const { map: balloonMap, list: balloonList } = buildBalloons(doc, ctx);
  const sheets = el("div", "sheets");
  (doc.sections || []).forEach((sec, si) => {
    const props = sec.properties || {};
    const pw = Math.round((props.pageSize?.width || 12240) * TWIP);
    const ph = Math.round((props.pageSize?.height || 15840) * TWIP);
    const m = props.pageMargin || {};
    const sheet = el("div", "sheet");
    const page = el("div", "page");
    page.style.width = `${pw}px`;
    page.style.minHeight = `${ph}px`;
    // Word's page: header band sits in the top margin, footer in the bottom
    // margin, text column is pageWidth - leftMargin - rightMargin.
    const hdr = Math.round((m.header ?? 720) * TWIP);
    page.style.padding = `${hdr}px ${(m.right || 1440) * TWIP}px ${hdr}px ${(m.left || 1440) * TWIP}px`;
    const content = el("div", "page-content");
    if (props.orientation === "landscape") content.classList.add("landscape");
    if (props.pageBorders) {
      content.classList.add("page-bordered");
      const b = props.pageBorders.top;
      if (b?.color && b.color !== "auto") content.style.borderColor = `#${b.color}`;
    }
    if (props.columns?.count > 1) content.classList.add("cols");
    (sec.children || []).forEach((c) => content.appendChild(renderNode(c, ctx)));

    // footnote + endnote areas
    if (ctx.footnotes.size) {
      const fa = el("div", "notes footnotes");
      fa.appendChild(el("div", "notes-rule"));
      [...ctx.footnotes.entries()].forEach(([id, f]) => {
        const line = el("div", "note-line");
        line.appendChild(el("sup", "note-ref", String(ctx.footnoteNumber(id))));
        const body = el("span", "note-body");
        (f.children || []).forEach((c) => body.appendChild(renderNode(c, ctx)));
        line.appendChild(body);
        fa.appendChild(line);
      });
      content.appendChild(fa);
    }
    if (ctx.endnotes.size) {
      const ea = el("div", "notes endnotes");
      ea.appendChild(el("div", "notes-rule"));
      [...ctx.endnotes.entries()].forEach(([id, f]) => {
        const line = el("div", "note-line");
        line.appendChild(el("sup", "note-ref", String(ctx.endnoteNumber(id))));
        const body = el("span", "note-body");
        (f.children || []).forEach((c) => body.appendChild(renderNode(c, ctx)));
        line.appendChild(body);
        ea.appendChild(line);
      });
      content.appendChild(ea);
    }

    // header / footer bands (office-open keeps them on the section object)
    const headerBand = el("div", "hf header");
    (sec.headers?.default || []).forEach((c) => headerBand.appendChild(renderNode(c, ctx)));
    if (!headerBand.children.length) headerBand.classList.add("empty");
    page.appendChild(headerBand);

    page.appendChild(content);

    const footerBand = el("div", "hf footer");
    (sec.footers?.default || []).forEach((c) => footerBand.appendChild(renderNode(c, ctx)));
    if (!footerBand.children.length) footerBand.classList.add("empty");
    page.appendChild(footerBand);

    const gutter = el("div", "gutter");
    sheet.appendChild(page);
    sheet.appendChild(gutter);
    sheet.appendChild(el("div", "sheet-label", `section ${si} — ${pw}×${ph}px${props.orientation ? ` (${props.orientation})` : ""}`));
    sheets.appendChild(sheet);
  });
  root.appendChild(sheets);
  root.appendChild(balloonList);
  return root;
}

/** Word puts comment balloons in the right-hand markup margin: anchor each
 *  balloon to the sheet that carries its comment reference. Runs after the
 *  tree is in the DOM so offsets are measurable. */
function anchorBalloons(root) {
  const map = new Map();
  root.querySelectorAll(".balloon").forEach((b) => map.set(b.dataset.cid, b));
  const placed = new Set();
  root.querySelectorAll(".comment-ref").forEach((ref) => {
    const id = String(ref.dataset.commentId);
    const b = map.get(id);
    if (!b) return;
    const sheet = ref.closest(".sheet");
    const gutter = sheet && sheet.querySelector(".gutter");
    if (!gutter) return;
    const page = ref.closest(".page");
    const pr = page.getBoundingClientRect();
    const rr = ref.getBoundingClientRect();
    gutter.appendChild(b);
    b.style.marginTop = `${Math.max(4, Math.round(rr.top - pr.top - 24))}px`;
    placed.add(id);
  });
  const leftover = root.querySelector(".balloons");
  if (leftover) {
    root.querySelectorAll(".balloon").forEach((b) => {
      if (!b.parentElement.classList.contains("gutter")) leftover.appendChild(b);
    });
  }
}

function buildBalloons(doc, ctx) {
  const map = new Map();
  const list = el("div", "balloons");
  const comments = doc.comments || [];
  if (!comments.length) return { map, list };
  list.appendChild(el("div", "balloons-title", `comments (${comments.length})`));
  comments.forEach((c) => {
    const b = el("div", "balloon");
    b.dataset.cid = String(c.id);
    b.appendChild(el("div", "balloon-head", `Commented [${c.initials || "?"}]:`));
    const body = el("div", "balloon-body");
    (c.children || []).forEach((ch) => body.appendChild(renderNode(ch, ctx)));
    b.appendChild(body);
    list.appendChild(b);
    map.set(String(c.id), b);
  });
  return { map, list };
}

// --------------------------------------------------------------------------
// boot
// --------------------------------------------------------------------------
const status = document.getElementById("status");
const out = document.getElementById("out");
const inputProbe = document.getElementById("input-probe");

/** Cleared before every load so a ready flag never survives a reload. */
function resetReady() {
  window.__OFFICEOPEN_READY__ = false;
  delete document.documentElement.dataset.officeopenReady;
  status.classList.remove("status-ok", "status-err");
  if (inputProbe) inputProbe.textContent = "";
}

/** Ready only after the rendered model has been through two animation frames. */
async function markReady(source, timings) {
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve(null)))
  );
  timings.ready_ms = Math.round(performance.now());
  window.__OFFICEOPEN_READY__ = true;
  document.documentElement.dataset.officeopenReady = "1";
  window.__OFFICEOPEN_TIMINGS__ = timings;
  status.textContent = `ready — rendered ${source}`;
  status.classList.add("status-ok");
}

function markError(err) {
  window.__OFFICEOPEN_READY__ = false;
  window.__OFFICEOPEN_ERROR__ = String(err && err.stack ? err.stack : err);
  status.textContent = "render failed";
  status.classList.add("status-err");
  out.appendChild(el("pre", "err", window.__OFFICEOPEN_ERROR__));
}

function report(doc, source) {
  console.log("[office-open] parsed with @office-open/docx parseDocument() from", source);
  console.log(
    "[office-open] sections=",
    (doc.sections || []).length,
    "paragraphStyles=",
    (doc.styles?.paragraphStyles || []).length,
    "comments=",
    (doc.comments || []).length,
    "footnotes=",
    (doc.footnotes || []).length,
    "endnotes=",
    (doc.endnotes || []).length
  );
  console.log("[office-open] construct census in parsed model:", JSON.stringify(census));
  console.log(
    "[office-open] explicit break markers: pageBreak=",
    census.pageBreak || 0,
    "columnBreak=",
    census.columnBreak || 0,
    "sections=",
    (doc.sections || []).length
  );
  console.log(
    "[office-open] pagination: office-open has no layout engine; model carries no page count."
  );
}

async function load(bytes, source) {
  resetReady();
  out.innerHTML = "";
  status.textContent = "parsing…";
  const timings = { started_ms: Math.round(performance.now()) };
  try {
    const doc = await parseDocument(bytes);
    timings.parse_ms = Math.round(performance.now()) - timings.started_ms;
    for (const k of Object.keys(census)) delete census[k];
    const view = renderDocument(doc);
    out.appendChild(view);
    anchorBalloons(view);
    timings.render_ms = Math.round(performance.now()) - timings.started_ms;
    window.__officeOpen = { doc, census };
    report(doc, source);
    await markReady(source, timings);
  } catch (e) {
    console.error("[office-open] parse failed", e);
    markError(e);
  }
}

/** The driver may intercept either route; the static host serves /corpus.docx. */
const CORPUS_ROUTES = ["/corpus.docx", "/sample.docx"];

async function fetchCorpus() {
  for (const route of CORPUS_ROUTES) {
    try {
      const res = await fetch(route);
      if (res.ok) return { route, bytes: await res.arrayBuffer() };
      console.log(`[office-open] ${route} not available:`, res.status);
    } catch (e) {
      console.log(`[office-open] ${route} fetch failed:`, e.message);
    }
  }
  return null;
}

async function boot() {
  const input = document.getElementById("corpus-file");
  input.addEventListener("change", async () => {
    const f = input.files && input.files[0];
    if (f) await load(await f.arrayBuffer(), f.name);
  });
  if (inputProbe) {
    inputProbe.addEventListener("input", () => {
      console.log(
        "[office-open] input probe (host contenteditable, not an office-open edit pipeline):",
        JSON.stringify(inputProbe.textContent)
      );
    });
  }
  // Preferred path: the host serves /corpus.docx, and the driver intercepts it.
  const corpus = await fetchCorpus();
  if (corpus) {
    await load(corpus.bytes, corpus.route);
    return;
  }
  status.textContent = "no sample served — pick a .docx";
}

boot();
