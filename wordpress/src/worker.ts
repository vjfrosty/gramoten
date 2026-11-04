/** The checker in its own thread, so that a long post never holds up typing. */

import { check, setData } from "./engine/index.ts";
import { loadData } from "./load.ts";
import type { Request, Response } from "./protocol.ts";

const send = (message: Response): void => postMessage(message);

/** Keeps its set while the words stay the same, so suggestions stay cached. */
let extraKey = "";
let extra: ReadonlySet<string> = new Set();

function wordsFor(words: string[]): ReadonlySet<string> {
  const key = words.join("\n");
  if (key !== extraKey) {
    extraKey = key;
    extra = new Set(words);
  }
  return extra;
}

let loading: Promise<boolean> = Promise.resolve(false);

self.onmessage = (event: MessageEvent<Request>) => {
  const message = event.data;
  if (message.type === "init") {
    const started = performance.now();
    loading = loadData(message.dataUrl, message.version).then(
      (data) => {
        setData(data);
        send({ type: "ready", ms: Math.round(performance.now() - started) });
        return true;
      },
      (error: unknown) => {
        send({ type: "failed", message: String(error) });
        return false;
      },
    );
    return;
  }
  loading.then((loaded) => {
    if (!loaded) return; // The editor already knows, from `failed`.
    const started = performance.now();
    try {
      const words = wordsFor(message.extra);
      const issues = message.texts.map((text) => check(text, words));
      send({ type: "checked", id: message.id, issues, ms: Math.round(performance.now() - started) });
    } catch (error) {
      // Better a message in the sidebar than a check that never ends.
      send({ type: "failed", message: String(error) });
    }
  });
};
