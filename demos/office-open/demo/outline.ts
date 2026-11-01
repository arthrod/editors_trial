type Json = Record<string, unknown>;

function isRecord(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value) && !(value instanceof Uint8Array);
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function inlineText(node: unknown): string {
  if (typeof node === "string") return node;
  if (!isRecord(node) && !Array.isArray(node)) return "";
  if (Array.isArray(node)) return node.map(inlineText).join("");

  const parts: string[] = [];
  if (typeof node.text === "string") parts.push(node.text);
  if (typeof node.deletedText === "string") parts.push(node.deletedText);
  if (typeof node.result === "string") parts.push(node.result);
  if (node.tab === true) parts.push("\t");
  if (node.carriageReturn === true || node.break === true) parts.push("\n");
  if (Array.isArray(node.children)) parts.push(inlineText(node.children));

  for (const key of [
    "hyperlink",
    "complexField",
    "simpleField",
    "sdt",
    "dir",
    "bdo",
    "inserted",
    "deleted",
    "movedFrom",
    "movedTo",
    "smartTag",
    "ruby",
    "altChunk",
    "customXml",
    "textbox",
  ]) {
    if (node[key] != null) parts.push(inlineText(node[key]));
  }

  if (isRecord(node.altChunk) || keyIsAlt(node)) {
    parts.push(altChunkText(node.altChunk ?? node));
  }

  return parts.join("");
}

function keyIsAlt(node: Json): boolean {
  return "data" in node && "contentType" in node && !("children" in node) && typeof node.text !== "string";
}

function altChunkText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value instanceof Uint8Array) return new TextDecoder().decode(value);
  if (!isRecord(value)) return "";
  if (typeof value.data === "string") return value.data;
  if (value.data instanceof Uint8Array) return new TextDecoder().decode(value.data);
  return "";
}

function headingTag(paragraph: Json): "h2" | "h3" | "h4" | "p" {
  const heading = paragraph.heading;
  if (typeof heading !== "string") return "p";
  const match = /Heading([1-9])/i.exec(heading);
  if (!match) return "p";
  const level = Number(match[1]);
  if (level <= 1) return "h2";
  if (level === 2) return "h3";
  return "h4";
}

function renderParagraph(paragraph: unknown): HTMLElement {
  const record = isRecord(paragraph) ? paragraph : {};
  const text = typeof paragraph === "string" ? paragraph : inlineText(record);
  return el(headingTag(record), "block", text);
}

function cellElement(cell: unknown): HTMLTableCellElement {
  const td = document.createElement("td");
  if (!isRecord(cell)) {
    td.textContent = inlineText(cell);
    return td;
  }
  if (typeof cell.columnSpan === "number" && cell.columnSpan > 1) td.colSpan = cell.columnSpan;
  if (typeof cell.rowSpan === "number" && cell.rowSpan > 1) td.rowSpan = cell.rowSpan;
  const blocks = Array.isArray(cell.children) ? cell.children : cell.sdt;
  if (Array.isArray(blocks)) td.append(...renderBlocks(blocks));
  else if (isRecord(cell.sdt) && Array.isArray(cell.sdt.cells)) {
    td.textContent = cell.sdt.cells.map(inlineText).join("");
  } else td.textContent = inlineText(cell);
  return td;
}

function renderTable(table: Json): HTMLTableElement {
  const html = document.createElement("table");
  const rows = Array.isArray(table.rows) ? table.rows : [];
  for (const row of rows) {
    const tr = document.createElement("tr");
    const cells = isRecord(row) && Array.isArray(row.cells)
      ? row.cells
      : isRecord(row) && isRecord(row.sdt) && Array.isArray(row.sdt.cells)
        ? row.sdt.cells
        : [];
    if (cells.length === 0) {
      const td = document.createElement("td");
      td.textContent = inlineText(row);
      tr.append(td);
    } else {
      for (const cell of cells) tr.append(cellElement(cell));
    }
    html.append(tr);
  }
  return html;
}

function renderBlock(node: unknown): HTMLElement | null {
  if (!isRecord(node)) {
    const text = inlineText(node);
    return text ? el("p", "block", text) : null;
  }
  if ("paragraph" in node) return renderParagraph(node.paragraph);
  if (isRecord(node.table)) return renderTable(node.table);
  if (isRecord(node.sdt)) {
    const wrap = el("div", "region");
    const kids = node.sdt.children ?? node.sdt.content;
    wrap.append(...renderBlocks(Array.isArray(kids) ? kids : []));
    return wrap;
  }
  if (isRecord(node.customXml)) {
    const wrap = el("div", "region");
    wrap.append(...renderBlocks(Array.isArray(node.customXml.children) ? node.customXml.children : []));
    return wrap;
  }
  if (isRecord(node.textbox)) {
    const wrap = el("div", "region");
    wrap.append(el("p", "region-label", "Text box"));
    wrap.append(...renderBlocks(Array.isArray(node.textbox.children) ? node.textbox.children : []));
    return wrap;
  }
  if ("altChunk" in node) {
    const text = altChunkText(node.altChunk);
    return el("p", "block", text || inlineText(node.altChunk));
  }
  if (isRecord(node.toc)) return el("p", "marker", "Table of contents");
  if ("subDoc" in node) return el("p", "marker", "Subdocument");
  if (typeof node.rawXml === "string") {
    const text = node.rawXml.replace(/<[^>]+>/g, "");
    return text.trim() ? el("p", "block", text) : null;
  }
  return null;
}

function renderBlocks(nodes: unknown[]): HTMLElement[] {
  const out: HTMLElement[] = [];
  for (const node of nodes) {
    const rendered = renderBlock(node);
    if (rendered) out.push(rendered);
  }
  return out;
}

function renderRegion(title: string, nodes: unknown[] | undefined): HTMLElement | null {
  if (!nodes?.length) return null;
  const wrap = el("div", "region");
  wrap.append(el("p", "region-label", title));
  wrap.append(...renderBlocks(nodes));
  return wrap;
}

export function renderOutline(doc: Json, root: HTMLElement): void {
  root.replaceChildren();
  const title = typeof doc.title === "string" && doc.title ? doc.title : "Document";
  root.append(el("h1", "doc-title", title));
  const meta = [doc.creator, doc.subject].filter((part) => typeof part === "string").join(" — ");
  if (meta) root.append(el("p", "doc-meta", meta));
  if (typeof doc.description === "string" && doc.description) {
    root.append(el("p", "doc-meta", doc.description));
  }

  const sections = Array.isArray(doc.sections) ? doc.sections : [];
  sections.forEach((section, index) => {
    root.append(el("p", "section-label", `Section ${index + 1}`));
    if (!isRecord(section)) return;
    root.append(...renderBlocks(Array.isArray(section.children) ? section.children : []));
    const headers = isRecord(section.headers) ? section.headers : {};
    const footers = isRecord(section.footers) ? section.footers : {};
    for (const [name, nodes] of Object.entries(headers)) {
      if (name === "partNames" || !Array.isArray(nodes)) continue;
      const region = renderRegion(`Header (${name})`, nodes);
      if (region) root.append(region);
    }
    for (const [name, nodes] of Object.entries(footers)) {
      if (name === "partNames" || !Array.isArray(nodes)) continue;
      const region = renderRegion(`Footer (${name})`, nodes);
      if (region) root.append(region);
    }
  });

  for (const [label, key] of [
    ["Footnotes", "footnotes"],
    ["Endnotes", "endnotes"],
    ["Comments", "comments"],
  ] as const) {
    const items = doc[key];
    if (!Array.isArray(items) || items.length === 0) continue;
    root.append(el("p", "section-label", label));
    for (const item of items) {
      if (isRecord(item) && Array.isArray(item.children)) root.append(...renderBlocks(item.children));
    }
  }
}

function summarize(value: unknown): string {
  if (value instanceof Uint8Array) return `Uint8Array(${value.byteLength})`;
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean" || value == null) return String(value);
  return "";
}

function renderJsonNode(value: unknown, key: string | null, depth: number): HTMLElement {
  if (Array.isArray(value)) {
    const details = document.createElement("details");
    if (depth < 2 || key === "sections" || key === "children" || key === "rows") details.open = true;
    details.append(el("summary", undefined, `${key ?? "array"} [${value.length}]`));
    const body = el("div");
    body.style.marginLeft = "12px";
    value.forEach((item, index) => body.append(renderJsonNode(item, String(index), depth + 1)));
    details.append(body);
    return details;
  }

  if (isRecord(value)) {
    const details = document.createElement("details");
    const keys = Object.keys(value);
    const interesting = key === "sections" || key === "paragraph" || key === "0" || depth < 1;
    if (interesting) details.open = true;
    details.append(el("summary", undefined, `${key ?? "object"} {${keys.length}}`));
    const body = el("div");
    body.style.marginLeft = "12px";
    for (const childKey of keys) body.append(renderJsonNode(value[childKey], childKey, depth + 1));
    details.append(body);
    return details;
  }

  const label = key == null ? summarize(value) : `${key}: ${summarize(value)}`;
  return el("p", "json-leaf", label);
}

export function renderJsonTree(doc: unknown, root: HTMLElement): void {
  root.replaceChildren();
  root.append(el("h2", undefined, "Raw JSON"));
  root.append(renderJsonNode(doc, null, 0));
}
