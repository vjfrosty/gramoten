// Builds plugin/build/: the editor script and the checker's worker.
//
//     npm run build
//
// The editor script uses the editor's own React and packages, through the `wp` global.

import { rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { build } from "esbuild";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outdir = join(root, "plugin", "build");
rmSync(outdir, { recursive: true, force: true });

// Streaming compilation needs the server to send .wasm as `application/wasm`, and shared
// hosts often do not. Compiling the downloaded bytes works whatever the type.
const anyWasmType = {
  name: "any-wasm-type",
  setup(b) {
    b.onLoad({ filter: /marisa-trie-wasm[\\/]src[\\/]marisa\.ts$/ }, async (args) => {
      const { readFile } = await import("node:fs/promises");
      const source = await readFile(args.path, "utf-8");
      const start = source.indexOf("async function compile(url: URL) {");
      const end = source.indexOf("export async function instantiate");
      if (start < 0 || end < 0) throw new Error("marisa-trie-wasm changed: review the any-wasm-type plugin");
      const compile =
        "async function compile(url: URL) {\n" +
        "  const response = await fetch(url);\n" +
        "  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);\n" +
        "  return WebAssembly.compile(await response.arrayBuffer());\n" +
        "}\n\n";
      return { contents: source.slice(0, start) + compile + source.slice(end), loader: "ts" };
    });
  },
};

const common = {
  bundle: true,
  minify: false,
  target: "es2022",
  charset: "utf8",
  logLevel: "info",
  legalComments: "inline",
};

await Promise.all([
  build({
    ...common,
    entryPoints: { editor: join(root, "src", "editor", "index.tsx") },
    outdir,
    format: "iife",
    jsx: "transform",
    jsxFactory: "wp.element.createElement",
    jsxFragment: "wp.element.Fragment",
  }),
  build({
    ...common,
    entryPoints: { worker: join(root, "src", "worker.ts") },
    outdir,
    format: "esm",
    assetNames: "[name]-[hash]",
    // Its source rather than its bundle, for the plugin above to patch.
    alias: { "marisa-trie-wasm": join(root, "node_modules", "marisa-trie-wasm", "src", "index.ts") },
    loader: { ".wasm": "file" },
    plugins: [anyWasmType],
  }),
]);
