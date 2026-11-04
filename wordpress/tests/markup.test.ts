import assert from "node:assert/strict";
import { test } from "node:test";

import { mapMarkup, replaceInMarkup } from "../src/editor/markup.ts";

const textOf = (source: string): string => mapMarkup(source).text;

function fix(source: string, wrong: string, right: string): string {
  const start = textOf(source).indexOf(wrong);
  assert.notEqual(start, -1, `${wrong} is not in the text`);
  return replaceInMarkup(source, [{ start, end: start + wrong.length, text: wrong, fix: right }]);
}

test("tags, comments, attributes and shortcodes are no text", () => {
  assert.equal(textOf('<p class="грещка">Един <b title="x>y">текст</b></p>'), "Един текст");
  assert.equal(textOf("а<!-- грещка -->б"), "аб");
  assert.equal(textOf('[gallery ids="1,2" title="грещка"]Текст[/gallery]'), "Текст");
  assert.equal(textOf('Преди [note/] след'), "Преди след");
});

test("text in square brackets that is no shortcode stays", () => {
  assert.equal(textOf("Виж [бележка на редактора] тук"), "Виж [бележка на редактора] тук");
  assert.equal(textOf("Виж [1] тук"), "Виж [1] тук");
});

test("code, scripts and styles are skipped", () => {
  assert.equal(textOf("<p>Текст <code>грещка</code> след</p>"), "Текст след");
  assert.equal(textOf("<script>var грещка = '<p>';</script><style>a{}</style>Текст"), "Текст");
  assert.equal(textOf("<pre>грещка</pre>"), "");
  assert.equal(textOf("Текст <svg><text>грещка</text></svg>"), "Текст");
});

test("block tags part lines, and layout spaces make no double spaces", () => {
  assert.equal(textOf("<div>\n    <p>Първи   ред.</p>\n    <p>Втори.</p>\n</div>"), "Първи ред.\nВтори.");
  assert.equal(textOf("Един<br>два<br/>три"), "Един\nдва\nтри");
  assert.equal(textOf("Първи абзац.\n\nВтори абзац.\nСъщият."), "Първи абзац.\nВтори абзац. Същият.");
});

test("entities are read as what they mean", () => {
  assert.equal(textOf("а&nbsp;б &amp; в &#1075; &#x433; &unknown;"), "а б & в г г &unknown;");
  assert.equal(textOf("😀 а"), "😀 а");
});

test("a fix changes only its text", () => {
  assert.equal(
    fix('<div class="грещка"><p>Има грещка тук.</p><!-- грещка --></div>', "грещка", "грешка"),
    '<div class="грещка"><p>Има грешка тук.</p><!-- грещка --></div>',
  );
  assert.equal(fix("<b>грещка</b>", "грещка", "грешка"), "<b>грешка</b>");
  assert.equal(fix('[note a="грещка"]Има грещка[/note]', "грещка", "грешка"), '[note a="грещка"]Има грешка[/note]');
});

test("offsets hold after emoji and entities", () => {
  assert.equal(fix("😀 &amp; &nbsp;грещка", "грещка", "грешка"), "😀 &amp; &nbsp;грешка");
});

test("what a fix writes is escaped", () => {
  assert.equal(fix("<p>а и б</p>", "и", "&"), "<p>а &amp; б</p>");
  assert.equal(fix("<p>а и б</p>", "и", "<"), "<p>а &lt; б</p>");
});

test("a fix over an entity replaces all of it", () => {
  assert.equal(fix("10&nbsp;лв", " ", " "), "10 лв");
  assert.equal(fix("а &amp; б", "&", "и"), "а и б");
});

test("a fix across markup is refused and the tags stay", () => {
  const source = "<p>Едно <b>две</b> три</p>";
  assert.equal(fix(source, "Едно две", "Нещо"), source);
});

test("a fix whose text moved on is refused", () => {
  const source = "<p>Има грещка</p>";
  assert.equal(replaceInMarkup(source, [{ start: 0, end: 3, text: "Няма", fix: "х" }]), source);
});

test("several fixes hold their places", () => {
  const source = "<p>едно <i>грещка</i> две грещка</p>";
  const text = textOf(source);
  const first = text.indexOf("грещка");
  const second = text.lastIndexOf("грещка");
  assert.equal(
    replaceInMarkup(source, [
      { start: first, end: first + 6, text: "грещка", fix: "грешка" },
      { start: second, end: second + 6, text: "грещка", fix: "грешка" },
    ]),
    "<p>едно <i>грешка</i> две грешка</p>",
  );
});

test("unclosed things do not hang or throw", () => {
  assert.equal(textOf("а < б"), "а < б");
  assert.equal(textOf("а <b"), "а <b");
  assert.equal(textOf("<!-- край"), "");
  assert.equal(textOf("<script>край"), "");
  assert.equal(textOf(""), "");
});
