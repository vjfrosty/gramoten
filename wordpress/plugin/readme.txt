=== Грамотен ===
Contributors: yasenivanov
Tags: bulgarian, spellcheck, grammar, proofreading, block editor
Requires at least: 6.6
Tested up to: 7.1
Requires PHP: 7.4
Stable tag: 0.1.0
License: GPL-3.0-or-later
License URI: https://www.gnu.org/licenses/gpl-3.0.html

Bulgarian spelling, grammar, punctuation and format checks in the block editor. Everything runs in your browser.

== Description ==

Грамотен проверява текста на български, докато пишете в редактора на блокове: правопис, граматика, пунктуация и формат. Грешките се подчертават в текста, а в страничния панел има обяснение и предложения за поправка.

* **Правопис:** думи извън речника, с предложения; латински букви, скрити в думи на кирилица.
* **Граматика:** пълен и кратък член, в/във и с/със, бройна форма, слято писане, „най-“ с дефис.
* **Пунктуация:** запетая пред съюзи и „който“, двойни знаци, незатворени скоби и кавички.
* **Формат:** тирета, кавички „…“, интервали, многоточие, цени в евро, дати и числа.

Проверката е по правила, без езиков модел и без услуга в интернет. **Текстът ви не излиза от браузъра.** Нищо не се променя без ваше потвърждение. Личният речник се пази в профила ви на този сайт.

Gramoten checks Bulgarian text as you write. It works by rule, with no language model and no external service: your text never leaves the browser, and nothing changes until you confirm it.

The checker is a TypeScript port of the [gramoten](https://github.com/vjfrosty/gramoten) Python package, and a test holds the two to the same results.

== Installation ==

1. Install and activate the plugin: from Plugins > Add Plugin, or by one of the ways below if you have the zip.
2. Open a post in the block editor, and the „Грамотен“ icon at the top right.

The zip is about 9.3 MB, because the dictionaries are inside it. Some hosts limit uploads to less, and WordPress then refuses the upload, sometimes with only "The link you followed has expired". Nothing is wrong with the zip. Any of these installs it without an upload:

* WP-CLI: `wp plugin install gramoten.zip --activate`
* FTP or your host's file manager: unpack the zip into `wp-content/plugins/`, so that you get `wp-content/plugins/gramoten/`, then activate the plugin.
* Ask your host to raise `upload_max_filesize` and `post_max_size` to 10 MB.

The word lists (about 15 MB) load once, the first time a post has Bulgarian text, and the browser keeps them after that.

== Frequently Asked Questions ==

= Does it send my text anywhere? =

No. The checker runs in your browser, on word lists that come from your own site. The plugin contacts no external service.

= Does it work with the Classic Editor, Elementor or other page builders? =

Not yet: only the block editor.

= Is everything underlined? =

Most text is. Two cases show in the sidebar only:

* Custom HTML, Classic and shortcode blocks, as the editor does not lay out their text word for word.
* The title, table cells and the Details summary in an older browser, as they need the CSS Custom Highlight API.

= Does it check Custom HTML, Classic and shortcode blocks? =

Yes: the text in them, not the tags, attributes, scripts or shortcode parameters. A fix changes only that text. Code blocks and `<code>` are not checked.

Since WordPress 7.1 a change made to a Custom HTML block from outside it stops undo from working, with or without this plugin. So there the sidebar lists the mistake and leaves the correction to you, in the block itself.

== Screenshots ==

1. Грешките са подчертани в текста, а в страничния панел има обяснение и предложения.
2. След „Поправи сигурните“: сигурните поправки са направени, правописът остава за вас.
3. Текстът в блоковете Custom HTML, Shortcode и Classic също се проверява, без таговете и атрибутите.

== Changelog ==

= 0.1.0 =
* First version.

== Third-party data and code ==

Source code, build tools and the scripts that build the word lists: https://github.com/vjfrosty/gramoten (see `wordpress/`).

* bgOffice Bulgarian dictionary, (C) 2001-2010 Radostin Radnev, used here under GPL-2.0-or-later.
* Chitanka misspelling table, (c) 2013 Authors of Chitanka, MIT.
* Leipzig Corpora Collection, word counts, CC BY: (c) 2025 Universität Leipzig / Sächsische Akademie der Wissenschaften / InfAI.
* EUR-Lex, (c) European Union, reused under Commission Decision 2011/833/EU.
* marisa-trie-wasm, (c) Patrick Gaskin, MIT; MARISA, (c) Susumu Yata, BSD-2-Clause or LGPL-2.1-or-later.

Details are in the NOTICE file.
