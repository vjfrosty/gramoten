/**
 * The plugin in real WordPress and a real browser. Exits non-zero when anything fails.
 *
 *   node run.mjs <site url> [--engine chromium|firefox|webkit] [--channel chrome]
 *                [--upload <zip>] [--remove-at-end] [--shots <dir>]
 *
 * The site comes from `@wp-playground/cli server --login`, which logs a new browser in as admin.
 */

import * as pw from "playwright-core";

const argv = process.argv.slice(2);
const site = argv[0];
const option = (name) => (argv.includes(name) ? argv[argv.indexOf(name) + 1] : undefined);
const engine = option("--engine") ?? "chromium";
const channel = option("--channel");
const upload = option("--upload");
const shots = option("--shots");
const removeAtEnd = argv.includes("--remove-at-end");

const browser = await pw[engine].launch({ headless: true, ...(channel ? { channel } : {}) });
const failures = [];
const problems = [];
let passed = 0;

function same(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) passed++;
  else failures.push(`${name}\n    expected ${e}\n    actual   ${a}`);
}
const yes = (name, value) => same(name, !!value, true);

async function scenario(name, fn) {
  const before = failures.length;
  try {
    await fn();
  } catch (e) {
    failures.push(`${name}: threw ${String(e.message).split("\n").slice(0, 3).join(" ")}`);
  }
  console.log(`${failures.length === before ? "ok  " : "FAIL"} ${name}`);
}

/** Errors that belong to WordPress or to what a scenario does on purpose. */
const EXPECTED = [
  /widgets\.php/, // A block theme has no widgets: WordPress answers 500, with or without the plugin.
  /403.*\/wp\/v2\/(settings|global-styles|users\/\d+)/, // What a contributor may not read, and the refused write below.
  /^contributor: pageerror (Object \{ message, code \}|\[object Object\])$/, // Firefox's and WebKit's words for the same; also without the plugin.
  /admin-ajax\.php due to access control checks/, // WebKit, as a page leaves mid-request; the plugin never calls admin-ajax.
];

function watch(page, where) {
  const add = (text) => {
    const line = `${where}: ${text}`;
    if (!EXPECTED.some((re) => re.test(line))) problems.push(line);
  };
  page.on("pageerror", (e) => add(`pageerror ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") add(`console ${m.text()} @ ${m.location().url}`);
  });
  page.on("requestfailed", (r) => {
    const reason = r.failure()?.errorText ?? "";
    // Leaving a page cancels what it was still loading; each browser words that differently.
    if (r.url().includes("gramoten") && !/ABORTED|NS_BINDING_ABORTED|cancelled/i.test(reason)) add(`failed ${r.url()} ${reason}`);
  });
  page.on("response", (r) => {
    if (r.url().includes("gramoten") && r.status() >= 400) add(`http ${r.status()} ${r.url()}`);
  });
  return page;
}

const settle = (page, ms = 2500) => page.waitForTimeout(ms);

async function openEditor(page, url = "/wp-admin/post-new.php") {
  await page.goto(`${site}${url}`, { waitUntil: "domcontentloaded", timeout: 180000 });
  await page.waitForFunction(() => window.wp?.data?.select("core/block-editor") && window.wp?.plugins, null, { timeout: 180000 });
  await page.waitForTimeout(2000);
  await page.evaluate(() => {
    wp.data.dispatch("core/preferences").set("core/edit-post", "welcomeGuide", false);
    wp.data.dispatch("core/edit-post").openGeneralSidebar("gramoten/gramoten");
  });
  await page.waitForTimeout(500);
}

const clearWords = (page) =>
  page.evaluate(() => wp.apiFetch({ path: "/wp/v2/users/me", method: "POST", data: { meta: { gramoten_words: [] } } }));

const words = (page) =>
  page.evaluate(() => wp.apiFetch({ path: "/wp/v2/users/me?context=edit" }).then((u) => u.meta.gramoten_words));

const insert = (page, blocks, title) =>
  page.evaluate(
    ({ blocks, title }) => {
      const make = ([name, attributes, inner]) => wp.blocks.createBlock(name, attributes, (inner ?? []).map(make));
      if (title) wp.data.dispatch("core/editor").editPost({ title });
      wp.data.dispatch("core/block-editor").insertBlocks(blocks.map(make));
    },
    { blocks, title },
  );

const findings = async (page) => {
  await page.waitForSelector(".gramoten-finding", { timeout: 120000 });
  await settle(page);
  return readFindings(page);
};
const readFindings = (page) =>
  page.locator(".gramoten-finding__text mark").evaluateAll((els) => els.map((e) => e.textContent));
const count = (list, value) => list.filter((x) => x === value).length;
const annotated = (page) =>
  page.frameLocator('iframe[name="editor-canvas"]').locator('[class*="annotation-text-gramoten"]').evaluateAll((els) => els.map((e) => e.textContent));
const highlighted = (page) =>
  page.evaluate(() => {
    const frame = document.querySelector('iframe[name="editor-canvas"]');
    const win = frame?.contentWindow ?? window;
    const read = (name) => [...(win.CSS.highlights.get(name) ?? [])].map((r) => r.toString());
    return { spelling: read("gramoten-spelling"), other: read("gramoten-other") };
  });
const content = (page) => page.evaluate(() => wp.data.select("core/editor").getEditedPostContent());
const blockAttribute = (page, name, attribute) =>
  page.evaluate(
    ({ name, attribute }) => {
      const find = (list) => {
        for (const b of list) {
          if (b.name === name) return b;
          const inner = find(b.innerBlocks);
          if (inner) return inner;
        }
        return null;
      };
      const block = find(wp.data.select("core/block-editor").getBlocks());
      return String(block?.attributes[attribute] ?? (block ? wp.blocks.getBlockContent(block) : ""));
    },
    { name, attribute },
  );

async function fixRow(page, wrong, right) {
  await page.locator(".gramoten-finding", { hasText: wrong }).first().getByRole("button", { name: right, exact: true }).click();
  await settle(page, 1200);
}
async function shot(page, name) {
  if (shots) await page.screenshot({ path: `${shots}/${engine}-${name}.png` });
}

const admin = watch(await (await browser.newContext({ viewport: { width: 1500, height: 1000 } })).newPage(), "admin");
const ROW = 'tr[data-plugin="gramoten/gramoten.php"]';

if (upload) {
  await scenario("the zip installs through the upload screen and activates", async () => {
    await admin.goto(`${site}/wp-admin/plugin-install.php?tab=upload`, { waitUntil: "domcontentloaded", timeout: 180000 });
    await admin.setInputFiles("#pluginzip", upload);
    await admin.click("#install-plugin-submit");
    const activate = admin.locator(".wrap a.button-primary", { hasText: /Activate/ });
    await activate.waitFor({ timeout: 180000 });
    await activate.click();
    await admin.waitForLoadState("domcontentloaded");
    await admin.goto(`${site}/wp-admin/plugins.php`, { waitUntil: "domcontentloaded" });
    yes("the plugin is active", await admin.locator(ROW).evaluate((e) => e.classList.contains("active")));
    same("no PHP message", /Fatal error|Parse error/.test(await admin.content()), false);
  });
}

await scenario("core: findings, underlines, one fix, dictionary, fix all, typing, saving", async () => {
  await openEditor(admin);
  await clearWords(admin);
  await openEditor(admin);
  await insert(
    admin,
    [
      ["core/paragraph", { content: "Незнам защо <strong>очудване</strong> е грешно, но радоста ми е голяма 😀 и отивам в Франция." }],
      ["core/list", {}, [["core/list-item", { content: "Хората дойдоха с запазени места" }]]],
      ["core/paragraph", { content: 'This is English text with "quotes" and it stays alone.' }],
    ],
    "Заглавие с грещка",
  );
  const found = await findings(admin);
  same("findings", found, ["грещка", "Незнам", "очудване", "радоста", "в", "с"]);
  same("annotations", await annotated(admin), ["Незнам", "очудване", "радоста", "в", "с"]);
  same("the title is underlined", (await highlighted(admin)).spelling, ["грещка"]);
  await shot(admin, "core");
  await fixRow(admin, "очудване", "учудване");
  yes("bold stays", (await content(admin)).includes("<strong>учудване</strong>"));
  yes("offset after the emoji still right", (await annotated(admin)).includes("в"));
  await fixRow(admin, "грещка", "грешка");
  same("title fixed", await admin.evaluate(() => wp.data.select("core/editor").getEditedPostAttribute("title")), "Заглавие с грешка");
  same("title underline gone", (await highlighted(admin)).spelling, []);
  await admin.locator(".gramoten-finding", { hasText: "радоста" }).getByRole("button", { name: "В речника" }).click();
  await settle(admin);
  same("word stored on the server", await words(admin), ["радоста"]);
  same("word no longer found", count(await readFindings(admin), "радоста"), 0);
  await admin.getByRole("button", { name: /Поправи сигурните/ }).click();
  await settle(admin);
  const fixed = await content(admin);
  yes("fix all: във", fixed.includes("отивам във Франция"));
  yes("fix all: със", fixed.includes("със запазени места"));
  yes("English untouched", fixed.includes('"quotes"'));
  const paragraph = admin.frameLocator('iframe[name="editor-canvas"]').locator('p[data-type="core/paragraph"]').first();
  await paragraph.click();
  await admin.keyboard.press("Control+End");
  await admin.keyboard.type(" Втора грешкка.", { delay: 20 });
  await settle(admin);
  yes("a typed mistake is found", (await readFindings(admin)).includes("грешкка"));
  await admin.evaluate(() => wp.data.dispatch("core/editor").savePost());
  await settle(admin, 3000);
  same("no trace in what is saved", /annotation|gramoten|highlight/.test(await content(admin)), false);
  await clearWords(admin);
});

await scenario("every kind of block is checked, and fixed in place", async () => {
  await openEditor(admin);
  await insert(
    admin,
    [
      ["core/quote", {}, [["core/paragraph", { content: "Цитат с грещка едно." }]]],
      ["core/columns", {}, [["core/column", {}, [["core/paragraph", { content: "Колона с грещка две." }]]]]],
      [
        "core/table",
        {
          head: [{ cells: [{ content: "Заглавна грещка клетка.", tag: "th" }, { content: "Втора без нищо.", tag: "th" }] }],
          body: [
            { cells: [{ content: "Клетка с <strong>грещка</strong> три.", tag: "td" }, { content: "Отивам в Франция.", tag: "td" }] },
            { cells: [{ content: "Друга клетка без нищо.", tag: "td" }, { content: "Последна с грещка.", tag: "td" }] },
          ],
          foot: [{ cells: [{ content: "Долна грещка клетка.", tag: "td" }, { content: "", tag: "td" }] }],
        },
      ],
      ["core/image", { url: "data:image/gif;base64,R0lGODlhAQABAAAAACw=", caption: "Надпис с грещка четири." }],
      ["core/buttons", {}, [["core/button", { text: "Бутон с грещка пет" }]]],
      ["core/verse", { content: "Стих с грещка шест." }],
      ["core/pullquote", { value: "Изваден с грещка седем." }],
      ["core/details", { summary: "Заглавие с грещка осем" }, [["core/paragraph", { content: "Подробност с грещка девет." }]]],
      ["core/preformatted", { content: "Готов с грещка единайсет." }],
      ["core/code", { content: "код с грещка десет" }],
      ["core/html", { content: '<div class="грещка"><p>Сурово с грещка.</p>\n  <code>грещка()</code><!-- грещка --></div>' }],
      ["core/shortcode", { text: '[note a="грещка"]Кратък с грещка.[/note]' }],
      ["core/freeform", { content: 'Класически с грещка.\n\n<a href="/грещка"><strong>Втори</strong></a> абзац.' }],
    ],
    "Заглавие с грещка",
  );
  const found = await findings(admin);
  same("one finding per text, none from code or attributes", count(found, "грещка"), 17);
  same("the certain one in a cell", count(found, "в"), 1);
  same("annotations", (await annotated(admin)).length, 8);
  same(
    "an underlined word keeps the colour of its block",
    await admin.frameLocator('iframe[name="editor-canvas"]').locator(".wp-block-button__link").evaluate((link) => {
      const word = link.querySelector('[class*="annotation-text-gramoten"]');
      return getComputedStyle(word).color === getComputedStyle(link).color;
    }),
    true,
  );
  const painted = await highlighted(admin);
  same("title, four cells and the summary are underlined", count(painted.spelling, "грещка"), 6);
  same("a certain finding in a cell, in its own colour", painted.other, ["в"]);
  await shot(admin, "blocks");

  // Typing in a cell moves the text: the underline follows.
  const canvas = admin.frameLocator('iframe[name="editor-canvas"]');
  await canvas.locator("tfoot td").first().click();
  await admin.keyboard.press("Home");
  await admin.keyboard.type("Ново ", { delay: 20 });
  await settle(admin);
  same("underlines after typing in a cell", count((await highlighted(admin)).spelling, "грещка"), 6);

  await admin.getByLabel("Подчертавай в текста").click();
  await settle(admin, 800);
  same("the switch turns them off", await highlighted(admin), { spelling: [], other: [] });
  same("and the annotations", await annotated(admin), []);
  await admin.getByLabel("Подчертавай в текста").click();
  await settle(admin, 800);
  same("and on", count((await highlighted(admin)).spelling, "грещка"), 6);

  // WordPress 7.1 hides Custom HTML's text from its attributes, and a write there breaks undo.
  const htmlReadOnly = await admin.evaluate(() => !("source" in wp.blocks.getBlockType("core/html").attributes.content));
  const fixable = admin.locator(".gramoten-finding", { hasText: "грещка" }).filter({ has: admin.getByRole("button", { name: "грешка", exact: true }) });
  for (let i = 0; i < 20 && (await fixable.count()); i++) {
    await fixable.first().getByRole("button", { name: "грешка", exact: true }).click();
    await settle(admin, 1200);
  }
  const html = await content(admin);
  same("what is left", count(await readFindings(admin), "грещка"), htmlReadOnly ? 1 : 0);
  yes("bold in a cell stays", html.includes("<strong>грешка</strong>"));
  same(
    "Custom HTML: only its text changed",
    await blockAttribute(admin, "core/html", "content"),
    `<div class="грещка"><p>Сурово с ${htmlReadOnly ? "грещка" : "грешка"}.</p>\n  <code>грещка()</code><!-- грещка --></div>`,
  );
  same("shortcode: only its text changed", await blockAttribute(admin, "core/shortcode", "text"), '[note a="грещка"]Кратък с грешка.[/note]');
  same(
    "Classic: only its text changed",
    await blockAttribute(admin, "core/freeform", "content"),
    'Класически с грешка.\n\n<a href="/грещка"><strong>Втори</strong></a> абзац.',
  );
  yes("code untouched", html.includes("код с грещка десет"));
  yes(
    "all blocks valid",
    await admin.evaluate(() => {
      const walk = (list) => list.every((b) => b.isValid && walk(b.innerBlocks));
      return walk(wp.data.select("core/block-editor").getBlocks());
    }),
  );
});

await scenario("one undo takes back fix all", async () => {
  await openEditor(admin);
  await insert(admin, [
    ["core/table", { body: [{ cells: [{ content: "Идвам с запазено място.", tag: "td" }] }] }],
    ["core/paragraph", { content: "Отивам в Франция днес." }],
    ["core/paragraph", { content: "Дойдоха с запазени места." }],
    ["core/shortcode", { text: "[note]Идвам с запазено място.[/note]" }],
    ["core/freeform", { content: "Идвам с запазено място." }],
    ["core/html", { content: "<p>Идвам с запазено място.</p>" }],
  ]);
  await findings(admin);
  const htmlReadOnly = await admin.evaluate(() => !("source" in wp.blocks.getBlockType("core/html").attributes.content));
  const start = await content(admin);
  const before = (await readFindings(admin)).length;
  same("the button counts only what it can fix", await admin.getByRole("button", { name: /Поправи сигурните/ }).innerText(), `Поправи сигурните (${htmlReadOnly ? 5 : 6})`);
  await admin.getByRole("button", { name: /Поправи сигурните/ }).click();
  await settle(admin);
  const fixed = await content(admin);
  same("what is left is what it may not touch", (fixed.match(/[ >]с запаз/g) ?? []).length, htmlReadOnly ? 1 : 0);
  same("all else fixed", / в Франц/.test(fixed), false);
  same("findings left", (await readFindings(admin)).length, htmlReadOnly ? 1 : 0);
  await admin.evaluate(() => wp.data.dispatch("core/editor").undo());
  await settle(admin);
  same("one undo restores everything", await content(admin), start);
  same("and the findings return", (await readFindings(admin)).length, before);
});

await scenario("skip, select, a fix after the text moved, sidebar closed", async () => {
  await openEditor(admin);
  await insert(admin, [["core/paragraph", { content: "Първа грещка тук и втора радоста." }]]);
  await findings(admin);
  await admin.locator(".gramoten-finding", { hasText: "радоста" }).getByRole("button", { name: "Пропусни" }).click();
  await settle(admin, 800);
  same("skipped", await readFindings(admin), ["грещка"]);
  await admin.evaluate(() => wp.data.dispatch("core/block-editor").clearSelectedBlock());
  await admin.locator(".gramoten-finding__text").first().click();
  same("a finding selects its block", await admin.evaluate(() => wp.data.select("core/block-editor").getSelectedBlock()?.name), "core/paragraph");
  await admin.evaluate(() => wp.data.dispatch("core/edit-post").closeGeneralSidebar());
  await settle(admin, 600);
  same("underlines stay with the sidebar closed", await annotated(admin), ["грещка"]);
  await admin.evaluate(() => wp.data.dispatch("core/edit-post").openGeneralSidebar("gramoten/gramoten"));
  await admin.waitForSelector(".gramoten-finding");
  await admin.evaluate(() => {
    const id = wp.data.select("core/block-editor").getBlocks()[0].clientId;
    wp.data.dispatch("core/block-editor").updateBlockAttributes(id, { content: "Нов текст. Първа грещка тук и втора радоста." });
  });
  await admin.locator(".gramoten-finding", { hasText: "грещка" }).getByRole("button", { name: "грешка", exact: true }).click();
  await settle(admin);
  same(
    "the fix finds its word, or leaves the text alone",
    await blockAttribute(admin, "core/paragraph", "content").then((t) => /^Нов текст\. Първа (грешка|грещка) тук и втора радоста\.$/.test(t)),
    true,
  );
});

await scenario("pages work too", async () => {
  await openEditor(admin, "/wp-admin/post-new.php?post_type=page");
  await insert(admin, [["core/paragraph", { content: "Страница с грещка." }]]);
  same("finding", await findings(admin), ["грещка"]);
  same("underline", await annotated(admin), ["грещка"]);
});

await scenario("a saved post reopens, publishes, and the public page is clean", async () => {
  await openEditor(admin);
  await insert(admin, [["core/table", { body: [{ cells: [{ content: "Запазена клетка с грещка.", tag: "td" }] }] }], ["core/paragraph", { content: "Запазен текст с грещка." }]], "Запазена статия");
  await findings(admin);
  await admin.evaluate(() => wp.data.dispatch("core/editor").savePost());
  await settle(admin, 3000);
  const id = await admin.evaluate(() => wp.data.select("core/editor").getCurrentPostId());
  await openEditor(admin, `/wp-admin/post.php?post=${id}&action=edit`);
  same("findings", await findings(admin), ["грещка", "грещка"]);
  same("cell underlined after reopening", (await highlighted(admin)).spelling, ["грещка"]);
  same("opening changes nothing", await admin.evaluate(() => wp.data.select("core/editor").isEditedPostDirty()), false);
  await admin.evaluate(() => {
    wp.data.dispatch("core/editor").editPost({ status: "publish" });
    return wp.data.dispatch("core/editor").savePost();
  });
  await settle(admin, 3000);
  const link = await admin.evaluate(() => wp.data.select("core/editor").getCurrentPost().link);
  const visitor = watch(await (await browser.newContext()).newPage(), "visitor");
  await visitor.goto(link, { waitUntil: "domcontentloaded" });
  const page = await visitor.content();
  await visitor.close();
  yes("the text is published", page.includes("Запазен текст"));
  same("no plugin on the public page", /gramoten|annotation-text/i.test(page), false);
});

await scenario("other screens load nothing of the checker", async () => {
  for (const path of ["/wp-admin/site-editor.php", "/wp-admin/edit.php", "/wp-admin/index.php", "/wp-admin/profile.php"]) {
    const page = watch(await admin.context().newPage(), path);
    const loaded = [];
    page.on("request", (r) => {
      if (/gramoten\/(build|data)\//.test(r.url())) loaded.push(r.url());
    });
    await page.goto(`${site}${path}`, { waitUntil: "domcontentloaded", timeout: 180000 });
    await page.waitForTimeout(4000);
    same(`${path}: no checker`, loaded, []);
    await page.close();
  }
});

await scenario("a contributor has a dictionary of their own", async () => {
  const login = `author${Date.now()}`;
  const password = "Test-pass-12345!";
  await openEditor(admin);
  const adminId = await admin.evaluate(() => wp.apiFetch({ path: "/wp/v2/users/me", method: "POST", data: { meta: { gramoten_words: ["грещка"] } } }).then((u) => u.id));
  await admin.evaluate(({ login, password }) => wp.apiFetch({ path: "/wp/v2/users", method: "POST", data: { username: login, password, email: `${login}@example.com`, roles: ["contributor"] } }), { login, password });
  const context = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
  await context.addCookies([{ name: "playground_auto_login_already_happened", value: "1", domain: new URL(site).hostname, path: "/" }]);
  const page = watch(await context.newPage(), "contributor");
  await page.goto(`${site}/wp-login.php`, { waitUntil: "domcontentloaded" });
  await page.fill("#user_login", login);
  await page.fill("#user_pass", password);
  await Promise.all([page.waitForURL(/wp-admin/, { timeout: 120000 }), page.click("#wp-submit")]);
  await openEditor(page);
  await insert(page, [["core/paragraph", { content: "Текст с грещка и радоста." }]]);
  same("the admin's word is not theirs", await findings(page), ["грещка", "радоста"]);
  await page.locator(".gramoten-finding", { hasText: "радоста" }).getByRole("button", { name: "В речника" }).click();
  await settle(page);
  same("their word is saved", await words(page), ["радоста"]);
  const refused = await page.evaluate((id) => wp.apiFetch({ path: `/wp/v2/users/${id}`, method: "POST", data: { meta: { gramoten_words: ["хак"] } } }).then(() => "allowed").catch((e) => e.code), adminId);
  same("another user's dictionary is refused", refused, "rest_cannot_edit");
  same("the admin's stays", await words(admin), ["грещка"]);
  same(
    "what is stored is cleaned",
    await admin.evaluate(() => wp.apiFetch({ path: "/wp/v2/users/me", method: "POST", data: { meta: { gramoten_words: ["  ДУМА ", "дума", "<b>тег</b>", ""] } } }).then((u) => u.meta.gramoten_words)),
    ["дума", "тег"],
  );
  await clearWords(admin);
  await page.close();
});

if (removeAtEnd) {
  await scenario("deactivates and deletes cleanly", async () => {
    await admin.goto(`${site}/wp-admin/plugins.php`, { waitUntil: "domcontentloaded" });
    await admin.locator(`${ROW} .deactivate a`).click();
    await admin.waitForLoadState("domcontentloaded");
    await settle(admin, 1000);
    await admin.goto(`${site}/wp-admin/post-new.php`, { waitUntil: "domcontentloaded" });
    await admin.waitForFunction(() => window.wp?.data?.select("core/block-editor"), null, { timeout: 180000 });
    await settle(admin, 3000);
    same("gone from the editor", await admin.evaluate(() => !!wp.plugins.getPlugin("gramoten")), false);
    await admin.goto(`${site}/wp-admin/plugins.php`, { waitUntil: "domcontentloaded" });
    admin.once("dialog", (d) => d.accept());
    await admin.locator(`${ROW} .delete a`).click();
    await settle(admin, 5000);
    await admin.goto(`${site}/wp-admin/plugins.php`, { waitUntil: "domcontentloaded" });
    same("gone from the list", await admin.locator(ROW).count(), 0);
  });
}

same("no errors in the browser", problems, []);
await browser.close();
console.log(`\n${engine}: ${passed} checks passed, ${failures.length} failed`);
for (const failure of failures) console.log(`\n- ${failure}`);
process.exit(failures.length ? 1 : 0);
