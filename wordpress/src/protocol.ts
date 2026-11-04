/** The messages between the editor and the checker's worker. */

import type { Issue } from "./engine/index.ts";

export type Request =
  | { type: "init"; dataUrl: string; version: string }
  | { type: "check"; id: number; texts: string[]; extra: string[] };

export type Response =
  | { type: "ready"; ms: number }
  | { type: "failed"; message: string }
  | { type: "checked"; id: number; issues: Issue[][]; ms: number };
