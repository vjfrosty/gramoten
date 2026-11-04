/**
 * The readable text of hand-written markup (Custom HTML, Classic and shortcode blocks), with
 * the place of each character in the source, so that a fix touches only that text.
 */

export interface Mapped {
  text: string;
  /** For each unit of `text`, where it starts and ends in the source. */
  starts: number[];
  ends: number[];
}

/** They end a line of text. */
const BREAKING = new Set(
  (
    "address article aside blockquote br caption center dd details div dl dt fieldset figcaption figure " +
    "footer form h1 h2 h3 h4 h5 h6 header hr li main nav ol p section summary table tbody td tfoot th " +
    "thead tr ul"
  ).split(" "),
);
/** What is inside them is no prose. */
const SKIPPED = new Set(
  "code kbd math noscript object pre samp script select style svg template textarea var".split(" "),
);
const ENTITIES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
  ndash: "–",
  mdash: "—",
  hellip: "…",
  laquo: "«",
  raquo: "»",
  bdquo: "„",
  ldquo: "“",
  rdquo: "”",
  lsquo: "‘",
  rsquo: "’",
};

const COMMENT = /<!--[\s\S]*?(?:-->|$)/y;
const TAG = /<(\/?)([a-zA-Z][\w:-]*)(?:[^>"']|"[^"]*"|'[^']*')*>/y;
const SHORTCODE = /\[\/?[a-zA-Z_][\w-]*(?:\s(?:[^\]"']|"[^"]*"|'[^']*')*)?\/?\]/y;
const ENTITY = /&(#\d+|#[xX][\da-fA-F]+|[a-zA-Z][a-zA-Z\d]*);/y;
const SPACES = /[ \t\r\n\f]+/y;

function matchAt(pattern: RegExp, source: string, at: number): RegExpExecArray | null {
  pattern.lastIndex = at;
  return pattern.exec(source);
}

function decode(body: string): string | null {
  if (body[0] !== "#") return ENTITIES[body] ?? null;
  const hex = body[1] === "x" || body[1] === "X";
  const code = Number.parseInt(body.slice(hex ? 2 : 1), hex ? 16 : 10);
  return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : null;
}

export function mapMarkup(source: string): Mapped {
  let text = "";
  const starts: number[] = [];
  const ends: number[] = [];
  const push = (value: string, start: number, end: number): void => {
    for (let i = 0; i < value.length; i++) {
      starts.push(start);
      ends.push(end);
    }
    text += value;
  };
  const breakLine = (at: number): void => {
    while (text.endsWith(" ")) {
      text = text.slice(0, -1);
      starts.pop();
      ends.pop();
    }
    if (text && !text.endsWith("\n")) push("\n", at, at);
  };

  let at = 0;
  while (at < source.length) {
    let found: RegExpExecArray | null;
    if ((found = matchAt(COMMENT, source, at)) || (found = matchAt(SHORTCODE, source, at))) {
      at += found[0].length;
    } else if ((found = matchAt(TAG, source, at))) {
      const name = found[2].toLowerCase();
      const closing = found[1] === "/";
      if (BREAKING.has(name)) breakLine(at);
      at += found[0].length;
      if (!closing && SKIPPED.has(name) && !found[0].endsWith("/>")) {
        const end = new RegExp(`</${name}\\s*>`, "ig");
        end.lastIndex = at;
        at = end.exec(source) ? end.lastIndex : source.length;
      }
    } else if ((found = matchAt(SPACES, source, at))) {
      const end = at + found[0].length;
      // An empty line parts paragraphs: Classic text holds them so, without tags.
      if ((found[0].match(/\n/g)?.length ?? 0) > 1) breakLine(at);
      else if (text && !text.endsWith(" ") && !text.endsWith("\n")) push(" ", at, end);
      at = end;
    } else if ((found = matchAt(ENTITY, source, at))) {
      const end = at + found[0].length;
      const decoded = decode(found[1]);
      if (decoded !== null) push(decoded, at, end);
      else push(found[0], at, end);
      at = end;
    } else {
      const point = String.fromCodePoint(source.codePointAt(at) as number);
      for (let i = 0; i < point.length; i++) push(point[i], at + i, at + i + 1);
      at += point.length;
    }
  }
  breakLine(source.length);
  while (text.endsWith("\n")) {
    text = text.slice(0, -1);
    starts.pop();
    ends.pop();
  }
  return { text, starts, ends };
}

export interface MarkupReplacement {
  start: number;
  end: number;
  /** What the span must still hold; otherwise the text moved on and it is skipped. */
  text: string;
  fix: string;
}

const escapeText = (value: string): string => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;");

/**
 * The source with the fixes in. A fix is skipped when the text moved on, or when its span has
 * markup inside, as replacing it would remove the tags too.
 */
export function replaceInMarkup(source: string, replacements: readonly MarkupReplacement[]): string {
  const { text, starts, ends } = mapMarkup(source);
  let out = source;
  let limit = Number.POSITIVE_INFINITY;
  for (const r of [...replacements].sort((a, b) => b.start - a.start)) {
    if (r.end > limit || text.slice(r.start, r.end) !== r.text) continue;
    let unbroken = true;
    for (let i = r.start; i < r.end - 1; i++) {
      if (ends[i] !== starts[i + 1] && !(starts[i] === starts[i + 1] && ends[i] === ends[i + 1])) unbroken = false;
    }
    if (!unbroken) continue;
    const from = r.end > r.start ? starts[r.start] : (starts[r.start] ?? source.length);
    const to = r.end > r.start ? ends[r.end - 1] : from;
    out = out.slice(0, from) + escapeText(r.fix) + out.slice(to);
    limit = r.start;
  }
  return out;
}
