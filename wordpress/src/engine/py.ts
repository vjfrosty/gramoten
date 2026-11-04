/**
 * Python's regular expressions and string methods, as the rules expect them.
 *
 * The rules keep their patterns as written in `src/gramoten/*.py`, so a rule here reads
 * like its original. `rx` turns such a pattern into a JavaScript one with Python's
 * meaning: `\w`, `\d`, `\s` and `\b` are Unicode-aware, `$` also matches before a final
 * line break, and a `[^\W_]` works, through the `v` flag's nested classes.
 *
 * Offsets are UTF-16 units, where Python's are code points: the block editor's are too.
 */

const WORD_CHARS = String.raw`\p{L}\p{N}_`;
const SPACE_CHARS = String.raw`\t-\r\x1c-\x20\x85\xa0  -     　`;
const WORD = `[${WORD_CHARS}]`;
const NON_WORD = `[^${WORD_CHARS}]`;
const END = String.raw`(?![\s\S])`;

/** Characters that are syntax inside a `v`-flag class, and so need a backslash there. */
const CLASS_SYNTAX = "()[]{}/|";

function translateClass(p: string, open: number): [string, number] {
  let out = "[";
  let i = open + 1;
  if (p[i] === "^") {
    out += "^";
    i++;
  }
  let afterEscapeClass = false;
  while (i < p.length && p[i] !== "]") {
    const ch = p[i];
    if (ch === "\\") {
      const next = p[++i];
      i++;
      afterEscapeClass = true;
      if (next === "w") out += WORD_CHARS;
      else if (next === "W") out += NON_WORD;
      else if (next === "d") out += String.raw`\p{Nd}`;
      else if (next === "D") out += String.raw`\P{Nd}`;
      else if (next === "s") out += SPACE_CHARS;
      else if (next === "S") out += `[^${SPACE_CHARS}]`;
      else if (next === "x" || next === "u") {
        const size = next === "x" ? 2 : 4;
        out += `\\${next}${p.slice(i, i + size)}`;
        i += size;
        afterEscapeClass = false;
      } else if (next === "-") out += String.raw`\-`;
      else if ("nrtfv".includes(next)) {
        out += `\\${next}`;
        afterEscapeClass = false;
      } else out += CLASS_SYNTAX.includes(next) ? `\\${next}` : next;
      continue;
    }
    if (ch === "-") {
      // A range only between two plain characters: `[а-я]`, not `[\w-]` or `[…,-]`.
      const range = !afterEscapeClass && out.length > 1 && !out.endsWith("^") && p[i + 1] !== "]";
      out += range ? "-" : String.raw`\-`;
      i++;
      afterEscapeClass = false;
      continue;
    }
    out += CLASS_SYNTAX.includes(ch) ? `\\${ch}` : ch;
    i++;
    afterEscapeClass = false;
  }
  return [`${out}]`, i + 1];
}

/** A Python pattern as a JavaScript pattern for the `v` flag. */
export function translate(p: string): string {
  let out = "";
  let i = 0;
  while (i < p.length) {
    const ch = p[i];
    if (ch === "[") {
      const [cls, next] = translateClass(p, i);
      out += cls;
      i = next;
    } else if (ch === "\\") {
      const next = p[i + 1];
      i += 2;
      if (next === "w") out += WORD;
      else if (next === "W") out += NON_WORD;
      else if (next === "d") out += String.raw`\p{Nd}`;
      else if (next === "D") out += String.raw`\P{Nd}`;
      else if (next === "s") out += `[${SPACE_CHARS}]`;
      else if (next === "S") out += `[^${SPACE_CHARS}]`;
      else if (next === "b") out += `(?:(?<=${WORD})(?!${WORD})|(?<!${WORD})(?=${WORD}))`;
      else if (next === "Z") out += END;
      else if (/[0-9xunrtfv]/.test(next) || "^$\\.*+?()[]{}|/".includes(next)) out += `\\${next}`;
      else out += next; // `\"`, `\-`, `\ `: the character itself
    } else if (ch === "$") {
      out += String.raw`(?=\n?${END})`;
      i++;
    } else if (ch === "{" && !/^\{\d*,?\d*\}/.test(p.slice(i))) {
      out += String.raw`\{`;
      i++;
    } else if (ch === "}" && !/\{\d*,?\d*$/.test(p.slice(0, i))) {
      out += String.raw`\}`;
      i++;
    } else {
      out += ch;
      i++;
    }
  }
  return out;
}

const compiled = new Map<string, RegExp>();

/** The compiled form of a Python pattern, with these extra JavaScript flags. */
export function rx(pattern: string, flags = ""): RegExp {
  const key = `${flags}/${pattern}`;
  let found = compiled.get(key);
  if (!found) {
    found = new RegExp(translate(pattern), `v${flags}`);
    compiled.set(key, found);
  }
  return found;
}

/** Flags in the rules' terms: `i` for `re.I`, `s` for `re.S`. */
export type Flags = "" | "i" | "s";

export interface Match {
  readonly index: number;
  /** The end of the whole match. */
  readonly end: number;
  /** The text of a group; `undefined` for one that took no part. */
  group(n?: number): string;
  start(n: number): number;
  stop(n: number): number;
}

function wrap(m: RegExpExecArray): Match {
  const indices = (m as RegExpExecArray & { indices: Array<[number, number]> }).indices;
  return {
    index: m.index,
    end: m.index + m[0].length,
    group: (n = 0) => m[n],
    start: (n) => indices[n][0],
    stop: (n) => indices[n][1],
  };
}

/** `re.finditer`. */
export function finditer(pattern: string, text: string, flags: Flags = ""): Match[] {
  const re = rx(pattern, `gd${flags}`);
  re.lastIndex = 0;
  const out: Match[] = [];
  for (let m = re.exec(text); m; m = re.exec(text)) {
    out.push(wrap(m));
    if (m[0] === "") re.lastIndex += 1;
  }
  return out;
}

/** `re.search`. */
export function search(pattern: string, text: string, flags: Flags = ""): Match | null {
  const m = rx(pattern, `d${flags}`).exec(text);
  return m && wrap(m);
}

/** `re.match`, from `pos`. */
export function match(pattern: string, text: string, pos = 0, flags: Flags = ""): Match | null {
  const re = rx(pattern, `yd${flags}`);
  re.lastIndex = pos;
  const m = re.exec(text);
  return m && wrap(m);
}

/** `re.fullmatch`. */
export function fullmatch(pattern: string, text: string, flags: Flags = ""): boolean {
  return rx(String.raw`^(?:${pattern})\Z`, flags).test(text);
}

/** `re.sub`. */
export function sub(
  pattern: string,
  replacement: string | ((m: string) => string),
  text: string,
  flags: Flags = "",
): string {
  const re = rx(pattern, `g${flags}`);
  re.lastIndex = 0;
  return typeof replacement === "string"
    ? text.replace(re, () => replacement)
    : text.replace(re, (m) => replacement(m));
}

const LOWER_OR_TITLE = /[\p{Lowercase}\p{Lt}]/v;
const UPPER = /\p{Uppercase}/v;

/** `str.isupper`: some cased character, and every cased one a capital. */
export function isUpper(s: string): boolean {
  return UPPER.test(s) && !LOWER_OR_TITLE.test(s);
}

/** `s[:1]`: the first character, not half of one. */
export function first(s: string): string {
  return s === "" ? "" : String.fromCodePoint(s.codePointAt(0) as number);
}

export function upperFirst(s: string): string {
  const head = first(s);
  return head.toUpperCase() + s.slice(head.length);
}

/** `str.capitalize`. */
export function capitalize(s: string): string {
  const head = first(s);
  return head.toUpperCase() + s.slice(head.length).toLowerCase();
}

const DIGIT =
  /[\p{Nd}\u{b2}-\u{b3}\u{b9}\u{1369}-\u{1371}\u{19da}\u{2070}\u{2074}-\u{2079}\u{2080}-\u{2089}\u{2460}-\u{2468}\u{2474}-\u{247c}\u{2488}-\u{2490}\u{24ea}\u{24f5}-\u{24fd}\u{24ff}\u{2776}-\u{277e}\u{2780}-\u{2788}\u{278a}-\u{2792}\u{10a40}-\u{10a43}\u{10e60}-\u{10e68}\u{11052}-\u{1105a}\u{1f100}-\u{1f10a}]/v;

/** Whether any character is a digit by `str.isdigit`. */
export function hasDigit(s: string): boolean {
  return DIGIT.test(s);
}

const SPACE_EDGE = new RegExp(`^[${SPACE_CHARS}]+|[${SPACE_CHARS}]+$`, "gv");
const SPACE_START = new RegExp(`^[${SPACE_CHARS}]+`, "v");

/** `str.strip`, with Python's idea of a space (no U+FEFF, but U+0085). */
export function strip(s: string): string {
  return s.replace(SPACE_EDGE, "");
}

export function lstrip(s: string): string {
  return s.replace(SPACE_START, "");
}

const ND = /\p{Nd}/v;

/** `int`, for the digits `\d` matches: a decimal digit of any script. */
export function toInt(digits: string): number {
  let out = 0;
  for (const ch of digits) {
    let zero = ch.codePointAt(0) as number;
    const at = zero;
    // Every script's digits are ten in a row: walk back to its zero.
    while (at - zero < 9 && ND.test(String.fromCodePoint(zero - 1))) zero--;
    out = out * 10 + (at - zero);
  }
  return out;
}

export function startsWithAny(s: string, starts: readonly string[]): boolean {
  return starts.some((x) => s.startsWith(x));
}

export function endsWithAny(s: string, ends: readonly string[]): boolean {
  return ends.some((x) => s.endsWith(x));
}

/** A cache of `fn` by its argument, emptied when full. */
export function memo<K, V>(fn: (key: K) => V, max: number): ((key: K) => V) & { clear(): void } {
  const cache = new Map<K, V>();
  const call = (key: K): V => {
    if (cache.has(key)) return cache.get(key) as V;
    if (cache.size >= max) cache.clear();
    const value = fn(key);
    cache.set(key, value);
    return value;
  };
  call.clear = () => cache.clear();
  return call;
}
