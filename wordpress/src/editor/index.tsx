/**
 * The block editor's side: a sidebar with the findings, and underlines in the text.
 *
 * Nothing leaves the browser: the checker runs in a worker, on word lists from this site.
 *
 * The editor renders a sidebar's content only while it is open, so the checking and the
 * underlines live in `Root`, which stays mounted, and the sidebar only shows the results.
 */

import type { Issue, Kind } from "../engine/index.ts";
import { Checker, type Status } from "./checker.ts";
import { applyReplacements, collectFields, type Field, isBulgarian } from "./fields.ts";
import { paint, type Painted } from "./highlights.ts";

const { useCallback, useEffect, useMemo, useRef, useState } = wp.element;
const { useDispatch, useRegistry, useSelect, dispatch, subscribe } = wp.data;
const { Button, Notice, PanelBody, Spinner, ToggleControl } = wp.components;
const { PluginSidebar, PluginSidebarMoreMenuItem } = wp.editor?.PluginSidebar ? wp.editor : wp.editPost;

const SIDEBAR = "gramoten";
const WAIT_AFTER_TYPING_MS = 500;
const REPAINT_WAIT_MS = 150;
const SOURCE = "gramoten";
/** Rows per group: a very long list helps nobody, and every row costs on each keystroke. */
const MAX_ROWS = 50;
const KINDS: ReadonlyArray<readonly [Kind, string]> = [
  ["spelling", "Правопис"],
  ["grammar", "Граматика"],
  ["punctuation", "Пунктуация"],
  ["format", "Формат"],
];

const checker = new Checker();

interface Finding {
  field: Field;
  issue: Issue;
}

const findingId = ({ field, issue }: Finding): string =>
  `${SOURCE}:${field.key}:${issue.start}:${issue.end}:${issue.code}`;

/** What "Пропусни" remembers for this session: the same mistake stays skipped when it moves. */
const skipKey = ({ issue }: Finding): string => `${issue.code}\u0001${issue.text}`;

function useFields(): Field[] {
  const blocks = useSelect((select: any) => select("core/block-editor").getBlocks(), []);
  const title = useSelect((select: any) => select("core/editor").getEditedPostAttribute("title") as string, []);
  return useMemo(() => collectFields(blocks, title ?? "").filter((f) => isBulgarian(f.text)), [blocks, title]);
}

function useStatus(): Status {
  const [status, setStatus] = useState(checker.status);
  useEffect(() => {
    checker.onStatus = setStatus;
    return () => {
      checker.onStatus = () => {};
    };
  }, []);
  return status;
}

/** The personal dictionary: in the user's own meta, on every device they write from. */
function useWords(): [string[], (word: string) => void] {
  const [words, setWords] = useState(gramotenConfig.words);
  const add = useCallback(
    (word: string) => {
      const next = [...new Set([...words, word.toLowerCase()])].sort();
      setWords(next);
      wp
        .apiFetch({ path: "/wp/v2/users/me", method: "POST", data: { meta: { gramoten_words: next } } })
        .catch(() => {
          dispatch("core/notices").createErrorNotice("Думата не се запази в речника.", { type: "snackbar" });
        });
    },
    [words],
  );
  return [words, add];
}

/** Each text's findings, by text: what did not change is not checked again. */
function useChecked(fields: Field[], words: string[]): { results: Map<string, Issue[]>; busy: boolean } {
  const [results, setResults] = useState(() => new Map<string, Issue[]>());
  const [busy, setBusy] = useState(false);
  const wordsKey = words.join("\n");
  const cache = useRef({ wordsKey, results: new Map<string, Issue[]>() });

  useEffect(() => {
    if (cache.current.wordsKey !== wordsKey) cache.current = { wordsKey, results: new Map() };
    const known = cache.current.results;
    const texts = [...new Set(fields.map((f) => f.text))];
    const missing = texts.filter((t) => !known.has(t));
    if (!missing.length) {
      setResults(new Map(texts.map((t) => [t, known.get(t) as Issue[]])));
      setBusy(false);
      return;
    }
    let cancelled = false;
    setBusy(true);
    const timer = setTimeout(() => {
      checker
        .check(missing, words)
        .then((issues) => {
          missing.forEach((text, i) => known.set(text, issues[i]));
          if (cancelled) return;
          // Only the texts in the post stay: an old version of a paragraph is not needed again.
          for (const text of known.keys()) if (!texts.includes(text)) known.delete(text);
          setResults(new Map(texts.map((t) => [t, known.get(t) as Issue[]])));
          setBusy(false);
        })
        .catch(() => {
          if (!cancelled) setBusy(false);
        });
    }, WAIT_AFTER_TYPING_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [fields, wordsKey]);

  return { results, busy };
}

/** Underlines what is listed: adds the new ones, removes the gone, and leaves the rest. */
function useUnderlines(findings: Finding[], enabled: boolean): void {
  const registry = useRegistry();
  const shown = useRef(new Set<string>());
  useEffect(() => {
    const annotations = dispatch("core/annotations");
    // An experimental API: without it the sidebar still works.
    if (!annotations?.__experimentalAddAnnotation) return;
    const wanted = new Map<string, Finding>();
    if (enabled) {
      for (const f of findings) {
        // A quiet finding is counted, never underlined.
        if (f.field.underline === "annotation" && !f.issue.quiet) wanted.set(findingId(f), f);
      }
    }
    registry.batch(() => {
      for (const id of shown.current) {
        if (!wanted.has(id)) {
          annotations.__experimentalRemoveAnnotation(id);
          shown.current.delete(id);
        }
      }
      for (const [id, f] of wanted) {
        if (shown.current.has(id)) continue;
        annotations.__experimentalAddAnnotation({
          id,
          source: f.issue.kind === "spelling" ? `${SOURCE}-spelling` : `${SOURCE}-other`,
          blockClientId: f.field.clientId,
          richTextIdentifier: f.field.attribute,
          range: { start: f.issue.start, end: f.issue.end },
        });
        shown.current.add(id);
      }
    });
  }, [findings, enabled]);
}

/**
 * The findings annotations cannot reach. The editor redraws their text on its own (typing, a
 * switch of preview), so they are painted again a moment after the editor's state changes.
 */
function useHighlights(findings: Finding[], enabled: boolean): void {
  useEffect(() => {
    const items: Painted[] = enabled
      ? findings
          .filter((f) => f.field.underline === "highlight" && !f.issue.quiet)
          .map(({ field, issue }) => ({
            field,
            start: issue.start,
            end: issue.end,
            text: issue.text,
            spelling: issue.kind === "spelling",
          }))
      : [];
    paint(items);
    if (!items.length) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const unsubscribe = subscribe(() => {
      clearTimeout(timer);
      timer = setTimeout(() => paint(items), REPAINT_WAIT_MS);
    });
    return () => {
      unsubscribe();
      clearTimeout(timer);
    };
  }, [findings, enabled]);
}

function useUnderlineSetting(): [boolean, (value: boolean) => void] {
  const [underline, setUnderline] = useState(() => {
    try {
      return localStorage.getItem("gramoten-underline") !== "0";
    } catch {
      return true;
    }
  });
  const set = useCallback((value: boolean) => {
    setUnderline(value);
    try {
      localStorage.setItem("gramoten-underline", value ? "1" : "0");
    } catch {
      // Only a convenience: it is back on at the next visit.
    }
  }, []);
  return [underline, set];
}

function FindingRow({
  finding,
  onApply,
  onSkip,
  onAddWord,
}: {
  finding: Finding;
  onApply: (f: Finding, fix: string) => void;
  onSkip: (f: Finding) => void;
  onAddWord: (word: string) => void;
}): JSX.Element {
  const { field, issue } = finding;
  const { selectBlock } = useDispatch("core/block-editor");
  const select = (): void => {
    if (field.clientId !== null) selectBlock(field.clientId);
  };
  const choices = field.readOnly ? [] : issue.suggestions.length ? issue.suggestions : issue.fix !== null ? [issue.fix] : [];
  return (
    <div className="gramoten-finding">
      <button type="button" className="gramoten-finding__text" onClick={select}>
        <mark className={`gramoten-mark gramoten-mark--${issue.kind === "spelling" ? "spelling" : "other"}`}>
          {issue.text.trim() || "␣"}
        </mark>
        <span className="gramoten-finding__where">{field.label}</span>
      </button>
      <p className="gramoten-finding__message">{issue.message_bg}</p>
      {field.readOnly && <p className="gramoten-finding__message">Поправете го в самия блок.</p>}
      <div className="gramoten-finding__actions">
        {choices.map((fix: string) => (
          <Button key={fix} variant="secondary" size="small" onClick={() => onApply(finding, fix)}>
            {fix === "" ? "Премахни" : fix.replaceAll(" ", "␣")}
          </Button>
        ))}
        {issue.kind === "spelling" && (
          <Button variant="tertiary" size="small" onClick={() => onAddWord(issue.text)}>
            В речника
          </Button>
        )}
        <Button variant="tertiary" size="small" onClick={() => onSkip(finding)}>
          Пропусни
        </Button>
      </div>
    </div>
  );
}

interface PanelProps {
  hasText: boolean;
  status: Status;
  busy: boolean;
  findings: Finding[];
  underline: boolean;
  setUnderline: (value: boolean) => void;
  onApply: (f: Finding, fix: string) => void;
  onSkip: (f: Finding) => void;
  onAddWord: (word: string) => void;
}

function Panel(props: PanelProps): JSX.Element {
  const { hasText, status, busy, findings, underline, setUnderline, onApply, onSkip, onAddWord } = props;
  const registry = useRegistry();

  const fixAll = (): void => {
    const byField = new Map<string, Finding[]>();
    for (const f of findings) {
      if (f.issue.fix !== null && !f.field.readOnly) byField.set(f.field.key, [...(byField.get(f.field.key) ?? []), f]);
    }
    // In one batch, so that one undo takes back all of it.
    registry.batch(() => {
      for (const list of byField.values()) {
        applyReplacements(
          list[0].field,
          list.map((f) => ({ start: f.issue.start, end: f.issue.end, text: f.issue.text, fix: f.issue.fix as string })),
        );
      }
    });
  };

  const visible = findings.filter((f) => !f.issue.quiet);
  const quiet = findings.length - visible.length;
  const certain = findings.filter((f) => f.issue.fix !== null && !f.field.readOnly).length;
  const loading = status.state === "loading";

  return (
    <>
      <PanelBody>
        {status.state === "failed" && (
          <Notice status="error" isDismissible={false}>
            Проверката не можа да се зареди: {status.message}
          </Notice>
        )}
        {loading && (
          <p>
            <Spinner /> Зареждане на речниците…
          </p>
        )}
        {status.state !== "failed" && !loading && !hasText && <p>Няма текст на български за проверка.</p>}
        {status.state === "ready" && hasText && !busy && !findings.length && <p>Няма забележки.</p>}
        {status.state === "ready" && busy && (
          <p>
            <Spinner /> Проверка…
          </p>
        )}
        {findings.length > 0 && (
          <p className="gramoten-summary">
            Забележки: <strong>{visible.length}</strong>
            {quiet > 0 ? ` (и ${quiet} дребни, само за автоматична поправка)` : ""}
          </p>
        )}
        {certain > 0 && (
          <Button variant="primary" onClick={fixAll}>
            Поправи сигурните ({certain})
          </Button>
        )}
        <ToggleControl
          __nextHasNoMarginBottom
          className="gramoten-toggle"
          label="Подчертавай в текста"
          checked={underline}
          onChange={setUnderline}
        />
      </PanelBody>
      {KINDS.map(([kind, label]) => {
        const list = visible.filter((f) => f.issue.kind === kind);
        return list.length ? (
          <PanelBody key={kind} title={`${label} (${list.length})`} initialOpen>
            {list.slice(0, MAX_ROWS).map((f) => (
              <FindingRow key={findingId(f)} finding={f} onApply={onApply} onSkip={onSkip} onAddWord={onAddWord} />
            ))}
            {list.length > MAX_ROWS && <p>Показани са първите {MAX_ROWS}. Поправете ги, за да видите следващите.</p>}
          </PanelBody>
        ) : null;
      })}
    </>
  );
}

const ICON = (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
    <path d="M5 4h11v2H7v12h4v2H5V4zm8.3 12.6 1.4-1.4 2.3 2.3 4.3-4.3 1.4 1.4-5.7 5.7-3.7-3.7z" />
  </svg>
);

function Root(): JSX.Element {
  const fields = useFields();
  const status = useStatus();
  const [words, addWord] = useWords();
  const { results, busy } = useChecked(fields, words);
  const [skipped, setSkipped] = useState(() => new Set<string>());
  const [underline, setUnderline] = useUnderlineSetting();

  const findings: Finding[] = useMemo(() => {
    const out: Finding[] = [];
    for (const field of fields) {
      for (const issue of results.get(field.text) ?? []) {
        const finding = { field, issue };
        if (!skipped.has(skipKey(finding))) out.push(finding);
      }
    }
    return out;
  }, [fields, results, skipped]);

  useUnderlines(findings, underline);
  useHighlights(findings, underline);

  const apply = useCallback((f: Finding, fix: string) => {
    applyReplacements(f.field, [{ start: f.issue.start, end: f.issue.end, text: f.issue.text, fix }]);
  }, []);
  const skip = useCallback((f: Finding) => setSkipped((s: Set<string>) => new Set(s).add(skipKey(f))), []);

  return (
    <>
      <PluginSidebarMoreMenuItem target={SIDEBAR} icon={ICON}>
        Грамотен
      </PluginSidebarMoreMenuItem>
      <PluginSidebar name={SIDEBAR} title="Грамотен" icon={ICON}>
        <Panel
          hasText={fields.length > 0}
          status={status}
          busy={busy}
          findings={findings}
          underline={underline}
          setUnderline={setUnderline}
          onApply={apply}
          onSkip={skip}
          onAddWord={addWord}
        />
      </PluginSidebar>
    </>
  );
}

wp.plugins.registerPlugin("gramoten", { icon: ICON, render: Root });
