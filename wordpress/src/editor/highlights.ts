/**
 * Underlines where annotations cannot reach: the title, table cells and the Details summary.
 *
 * The CSS Custom Highlight API paints over the text without touching the page, so nothing can
 * end up in the saved post. A browser without it shows these findings in the sidebar only.
 */

import type { Field } from "./fields.ts";

export interface Painted {
  field: Field;
  start: number;
  end: number;
  text: string;
  spelling: boolean;
}

function editorDocument(): Document {
  const frame = document.querySelector<HTMLIFrameElement>('iframe[name="editor-canvas"]');
  return frame?.contentDocument ?? document;
}

function elementOf(doc: Document, field: Field): Element | null {
  if (field.clientId === null) return doc.querySelector(".editor-post-title__input");
  const block = doc.querySelector(`[data-block="${field.clientId}"]`);
  if (!block) return null;
  if (field.cell) {
    const section = block.querySelector<HTMLTableSectionElement>(`t${field.cell.section}`);
    return section?.rows[field.cell.row]?.cells[field.cell.column] ?? null;
  }
  return block.querySelector("summary");
}

/** The span of plain text in the DOM; a line break counts as one, as in the editor's text. */
function rangeIn(doc: Document, element: Element, item: Painted): Range | null {
  const walker = doc.createTreeWalker(element, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  const range = doc.createRange();
  let at = 0;
  let started = false;
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      if ((node as Element).hasAttribute("data-rich-text-line-break")) at += 1;
      continue;
    }
    const length = (node.nodeValue as string).length;
    if (!started && item.start < at + length) {
      range.setStart(node, item.start - at);
      started = true;
    }
    if (started && item.end <= at + length) {
      range.setEnd(node, item.end - at);
      // The text may have moved on since the check.
      return range.toString().replaceAll("\n", "") === item.text.replaceAll("\n", "") ? range : null;
    }
    at += length;
  }
  return null;
}

export function paint(items: readonly Painted[]): void {
  const doc = editorDocument();
  const win = doc.defaultView as (Window & typeof globalThis) | null;
  if (!win?.CSS?.highlights || !win.Highlight) return;
  const spelling = new win.Highlight();
  const other = new win.Highlight();
  for (const item of items) {
    const element = elementOf(doc, item.field);
    const range = element && rangeIn(doc, element, item);
    if (range) (item.spelling ? spelling : other).add(range);
  }
  win.CSS.highlights.set("gramoten-spelling", spelling);
  win.CSS.highlights.set("gramoten-other", other);
}
