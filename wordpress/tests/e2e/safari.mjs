/**
 * The core of the plugin in real Safari, which only runs on a Mac and only through WebDriver:
 *
 *   sudo safaridriver --enable
 *   node safari.mjs <site url>
 *
 * BROWSER=chrome runs the same steps elsewhere, to test this script itself.
 */

import { Builder, until, By } from "selenium-webdriver";
import chrome from "selenium-webdriver/chrome.js";

const site = process.argv[2];
const driver = await new Builder()
  .forBrowser(process.env.BROWSER ?? "safari")
  .setChromeOptions(new chrome.Options().addArguments("--headless=new", "--window-size=1500,1000"))
  .build();
const failures = [];

function same(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  console.log(`${a === e ? "ok  " : "FAIL"} ${name}`);
  if (a !== e) failures.push(`${name}\n    expected ${e}\n    actual   ${a}`);
}
const wait = (ms) => driver.sleep(ms);
const run = (body, ...args) => driver.executeScript(body, ...args);

try {
  await driver.manage().setTimeouts({ script: 120000 });
  await driver.get(`${site}/wp-admin/post-new.php`);
  await driver.wait(() => run("return !!(window.wp && wp.data && wp.plugins && wp.data.select('core/block-editor'))"), 180000);
  await driver.executeAsyncScript(`
    const done = arguments[arguments.length - 1];
    wp.apiFetch({ path: "/wp/v2/users/me", method: "POST", data: { meta: { gramoten_words: [] } } }).then(() => done());
  `);
  await driver.navigate().refresh();
  await driver.wait(() => run("return !!(window.wp && wp.data && wp.plugins && wp.data.select('core/block-editor'))"), 180000);
  await wait(2500);
  console.log(await run("return navigator.userAgent"));
  await run(`
    window.__errors = [];
    window.addEventListener("error", (e) => window.__errors.push(e.message));
    wp.data.dispatch("core/preferences").set("core/edit-post", "welcomeGuide", false);
    wp.data.dispatch("core/edit-post").openGeneralSidebar("gramoten/gramoten");
    wp.data.dispatch("core/editor").editPost({ title: "Заглавие с грещка" });
    wp.data.dispatch("core/block-editor").insertBlocks([
      wp.blocks.createBlock("core/paragraph", { content: "Незнам защо <strong>очудване</strong> 😀 е грешно и отивам в Франция." }),
      wp.blocks.createBlock("core/table", { body: [{ cells: [{ content: "Клетка с грещка.", tag: "td" }] }] }),
      wp.blocks.createBlock("core/html", { content: '<p class="грещка">Сурово с грещка.</p>' }),
    ]);
  `);
  await driver.wait(until.elementLocated(By.css(".gramoten-finding")), 180000);
  await wait(3000);

  const findings = () => run(`return [...document.querySelectorAll(".gramoten-finding__text mark")].map((e) => e.textContent)`);
  same("findings", await findings(), ["грещка", "Незнам", "очудване", "грещка", "грещка", "в"]);
  same(
    "annotations",
    await run(`
      const doc = document.querySelector('iframe[name="editor-canvas"]').contentDocument;
      return [...doc.querySelectorAll('[class*="annotation-text-gramoten"]')].map((e) => e.textContent);
    `),
    ["Незнам", "очудване", "в"],
  );
  same(
    "title and cell underlined",
    await run(`
      const win = document.querySelector('iframe[name="editor-canvas"]').contentWindow;
      return win.CSS.highlights ? [...win.CSS.highlights.get("gramoten-spelling")].map((r) => r.toString()) : "no highlight API";
    `),
    ["грещка", "грещка"],
  );
  await run(`
    const rows = [...document.querySelectorAll(".gramoten-finding")];
    const row = rows.find((r) => r.textContent.includes("очудване"));
    [...row.querySelectorAll("button")].find((b) => b.textContent === "учудване").click();
  `);
  await wait(2000);
  same(
    "a fix keeps the bold",
    await run(`return wp.data.select("core/editor").getEditedPostContent().includes("<strong>учудване</strong>")`),
    true,
  );
  await run(`[...document.querySelectorAll("button")].find((b) => b.textContent.startsWith("Поправи сигурните")).click();`);
  await wait(2000);
  same("fix all", await run(`return wp.data.select("core/editor").getEditedPostContent().includes("отивам във Франция")`), true);
  same("no errors", await run("return window.__errors"), []);
} finally {
  await driver.quit();
}
for (const failure of failures) console.log(`\n- ${failure}`);
process.exit(failures.length ? 1 : 0);
