/** The text of a post, as the editor holds it: each text attribute of each block. */

import { mapMarkup, replaceInMarkup } from "./markup.ts";

export interface Field {
  /** Stable while the block lives; the title has none. */
  key: string;
  clientId: string | null;
  attribute: string;
  /** A table's cell: its text sits inside the block's rows, not in an attribute of its own. */
  cell?: Cell;
  /** Hand-written markup, not rich text: the offsets count in `mapMarkup`'s text. */
  markup?: boolean;
  /** Findings only: writing here would cost the user their undo. */
  readOnly?: boolean;
  /** How its findings show in the text: `none` is the sidebar only. */
  underline: "annotation" | "highlight" | "none";
  /** The plain text: the offsets of annotations and findings count in it. */
  text: string;
  label: string;
}

interface Cell {
  section: string;
  row: number;
  column: number;
}

export const TITLE_KEY = "post-title";

/** Code is not prose: its words are no mistakes. */
const NOT_PROSE = new Set(["core/code"]);
const TABLE_SECTIONS = ["head", "body", "foot"];
/** Blocks that hold markup as written, by the attribute that holds it. */
const MARKUP_BLOCKS: Record<string, string> = {
  "core/html": "content",
  "core/freeform": "content",
  "core/shortcode": "text",
};

function richAttributes(blockName: string): string[] {
  const type = wp.blocks.getBlockType(blockName);
  if (!type) return [];
  return Object.entries(type.attributes as Record<string, { source?: string }>)
    .filter(([, schema]) => schema.source === "html" || schema.source === "rich-text")
    .map(([name]) => name);
}

/**
 * The source of a markup block. WordPress 7.1 keeps Custom HTML's text out of the attributes it
 * hands out, though it still writes it: what the block saves is the same text on every version.
 * A write to such a text also stops undo from working, with or without this plugin, so
 * `readOnly` keeps those fields to their findings.
 */
function markupSource(block: any, attribute: string): string {
  return String(block.attributes[attribute] ?? wp.blocks.getBlockContent(block) ?? "");
}

/** Plain text by HTML: a keystroke changes one field, and the others need no parsing again. */
const plainText = new Map<string, string>();
const PLAIN_TEXT_MAX = 5000;

function toPlainText(html: string): string {
  return cachedText(html, () => wp.richText.create({ html }).text as string);
}

function markupToText(source: string): string {
  return cachedText(`markup\u0001${source}`, () => mapMarkup(source).text);
}

function cachedText(key: string, parse: () => string): string {
  let text = plainText.get(key);
  if (text === undefined) {
    text = parse();
    if (plainText.size >= PLAIN_TEXT_MAX) plainText.clear();
    plainText.set(key, text);
  }
  return text;
}

/** Every text field of the post, in reading order. */
export function collectFields(blocks: any[], title: string): Field[] {
  const out: Field[] = [];
  if (title) {
    out.push({ key: TITLE_KEY, clientId: null, attribute: "title", underline: "highlight", text: title, label: "Заглавие" });
  }
  const walk = (list: any[]): void => {
    for (const block of list) {
      if (NOT_PROSE.has(block.name)) continue;
      const type = wp.blocks.getBlockType(block.name);
      const markupAttribute = MARKUP_BLOCKS[block.name];
      if (markupAttribute) {
        const text = markupToText(markupSource(block, markupAttribute));
        if (text) {
          out.push({
            key: `${block.clientId}:${markupAttribute}`,
            clientId: block.clientId,
            attribute: markupAttribute,
            markup: true,
            readOnly: block.attributes[markupAttribute] === undefined,
            underline: "none",
            text,
            label: type?.title ?? block.name,
          });
        }
        continue;
      }
      if (block.name === "core/table") {
        for (const section of TABLE_SECTIONS) {
          (block.attributes[section] ?? []).forEach((row: any, rowIndex: number) => {
            row.cells.forEach((cell: any, column: number) => {
              const text = toPlainText(String(cell.content ?? ""));
              if (!text) return;
              const attribute = `${section}.${rowIndex}.${column}`;
              out.push({
                key: `${block.clientId}:${attribute}`,
                clientId: block.clientId,
                attribute,
                cell: { section, row: rowIndex, column },
                underline: "highlight",
                text,
                label: type?.title ?? block.name,
              });
            });
          });
        }
      }
      for (const attribute of richAttributes(block.name)) {
        const value = block.attributes[attribute];
        if (value === undefined || value === null || String(value) === "") continue;
        const text = toPlainText(String(value));
        if (text) {
          out.push({
            key: `${block.clientId}:${attribute}`,
            clientId: block.clientId,
            attribute,
            // Older WordPress leaves the summary without what annotations need.
            underline: block.name === "core/details" && attribute === "summary" ? "highlight" : "annotation",
            text,
            label: type?.title ?? block.name,
          });
        }
      }
      walk(block.innerBlocks ?? []);
    }
  };
  walk(blocks);
  return out;
}

const CYRILLIC = /[Ѐ-ӿ]/u;

/** Text with no Cyrillic in it is not Bulgarian: nothing here applies to it. */
export function isBulgarian(text: string): boolean {
  return CYRILLIC.test(text);
}

export interface Replacement {
  start: number;
  end: number;
  /** What the span must still hold; otherwise the text moved on and it is skipped. */
  text: string;
  fix: string;
}

function replaced(value: any, replacements: readonly Replacement[]): { value: any; changed: boolean } {
  let current = value;
  let changed = false;
  // From the end, so the earlier offsets still hold.
  const ordered = [...replacements].sort((a, b) => b.start - a.start);
  let limit = Number.POSITIVE_INFINITY;
  for (const r of ordered) {
    if (r.end > limit || (current.text as string).slice(r.start, r.end) !== r.text) continue;
    // The new text takes the formatting of what it replaces: a bold word stays bold.
    const formats = current.formats[r.start];
    const next = wp.richText.insert(current, r.fix, r.start, r.end);
    for (let i = 0; i < r.fix.length; i++) next.formats[r.start + i] = formats;
    current = next;
    changed = true;
    limit = r.start;
  }
  return { value: current, changed };
}

/** The changes made through the data store, so that undo and the dirty state work. */
export function applyReplacements(field: Field, replacements: readonly Replacement[]): boolean {
  if (field.readOnly) return false;
  if (field.clientId === null) {
    let title = field.text;
    let limit = Number.POSITIVE_INFINITY;
    for (const r of [...replacements].sort((a, b) => b.start - a.start)) {
      if (r.end > limit || title.slice(r.start, r.end) !== r.text) continue;
      title = title.slice(0, r.start) + r.fix + title.slice(r.end);
      limit = r.start;
    }
    if (title === field.text) return false;
    wp.data.dispatch("core/editor").editPost({ title });
    return true;
  }
  const blockEditor = wp.data.select("core/block-editor");
  const attributes = blockEditor.getBlockAttributes(field.clientId);
  if (field.markup) {
    const block = blockEditor.getBlock(field.clientId);
    if (!block) return false;
    const source = markupSource(block, field.attribute);
    const next = replaceInMarkup(source, replacements);
    if (next === source) return false;
    wp.data.dispatch("core/block-editor").updateBlockAttributes(field.clientId, { [field.attribute]: next });
    return true;
  }
  const { cell } = field;
  const current = cell
    ? attributes?.[cell.section]?.[cell.row]?.cells?.[cell.column]?.content
    : attributes?.[field.attribute];
  if (current === undefined) return false;
  const { value, changed } = replaced(wp.richText.create({ html: String(current) }), replacements);
  if (!changed) return false;
  const html = wp.richText.toHTMLString({ value });
  const RichTextData = wp.richText.RichTextData;
  const next = typeof current !== "string" && RichTextData ? RichTextData.fromHTMLString(html) : html;
  const update = cell
    ? {
        [cell.section]: attributes[cell.section].map((row: any, r: number) =>
          r !== cell.row
            ? row
            : { ...row, cells: row.cells.map((c: any, i: number) => (i !== cell.column ? c : { ...c, content: next })) },
        ),
      }
    : { [field.attribute]: next };
  wp.data.dispatch("core/block-editor").updateBlockAttributes(field.clientId, update);
  return true;
}
