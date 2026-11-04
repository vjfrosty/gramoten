/** The editor's side of the worker: starts it on first use, and answers by promise. */

import type { Issue } from "../engine/index.ts";
import type { Request, Response } from "../protocol.ts";

export type Status = { state: "idle" | "loading" | "ready" } | { state: "failed"; message: string };

/** A module worker must come from the page's origin: a plugin URL on a CDN goes through a blob. */
function startWorker(url: string): Worker {
  if (new URL(url, location.href).origin === location.origin) return new Worker(url, { type: "module" });
  const code = `import ${JSON.stringify(url)};`;
  return new Worker(URL.createObjectURL(new Blob([code], { type: "text/javascript" })), { type: "module" });
}

export class Checker {
  status: Status = { state: "idle" };
  onStatus: (status: Status) => void = () => {};

  private worker: Worker | null = null;
  private next = 1;
  private waiting = new Map<number, { resolve: (issues: Issue[][]) => void; reject: (error: Error) => void }>();

  private setStatus(status: Status): void {
    this.status = status;
    this.onStatus(status);
  }

  private fail(message: string): void {
    this.setStatus({ state: "failed", message });
    for (const { reject } of this.waiting.values()) reject(new Error(message));
    this.waiting.clear();
  }

  private start(): Worker {
    if (this.worker) return this.worker;
    this.setStatus({ state: "loading" });
    const worker = startWorker(gramotenConfig.workerUrl);
    worker.onerror = (event) => this.fail(event.message || "The checker could not start");
    worker.onmessage = (event: MessageEvent<Response>) => {
      const message = event.data;
      if (message.type === "ready") {
        this.setStatus({ state: "ready" });
      } else if (message.type === "failed") {
        this.fail(message.message);
      } else {
        this.waiting.get(message.id)?.resolve(message.issues);
        this.waiting.delete(message.id);
      }
    };
    const init: Request = { type: "init", dataUrl: gramotenConfig.dataUrl, version: gramotenConfig.version };
    worker.postMessage(init);
    this.worker = worker;
    return worker;
  }

  check(texts: string[], extra: string[]): Promise<Issue[][]> {
    if (this.status.state === "failed") return Promise.reject(new Error(this.status.message));
    const worker = this.start();
    const id = this.next++;
    return new Promise((resolve, reject) => {
      this.waiting.set(id, { resolve, reject });
      const request: Request = { type: "check", id, texts, extra };
      worker.postMessage(request);
    });
  }
}
