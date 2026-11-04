/** The editor's globals. WordPress provides them; only the names used here are typed. */

declare const wp: {
  // biome-ignore lint: WordPress ships these packages untyped at run time.
  [name: string]: any;
};

declare const gramotenConfig: {
  workerUrl: string;
  dataUrl: string;
  version: string;
  words: string[];
};

declare namespace JSX {
  type Element = unknown;
  interface IntrinsicAttributes {
    key?: string;
  }
  interface IntrinsicElements {
    // biome-ignore lint: plain HTML elements, as the editor renders them.
    [name: string]: any;
  }
}
