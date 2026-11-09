/** Port of `src/gramoten/grammar.py`: Bulgarian agreement, by rule, with the morphology. */

import { once, text as dataText } from "./data.ts";
import type { Hit } from "./lexical.ts";
import { analyse, forms, inflect, type Reading } from "./morphology.ts";
import { endsWithAny, finditer, first, fullmatch, isUpper, match, search, sub, upperFirst } from "./py.ts";
import { byPosition, normalise } from "./punctuation.ts";
import { before } from "./tokenize.ts";

const WORD = "[А-Яа-яЍѝ]+(?:-[А-Яа-яЍѝ]+)*";
const MODIFIER_POS: ReadonlySet<string> = new Set(["A", "Pposs", "Pdemo", "Mo"]);
const ATTRIBUTE_PARTICIPLES = ["ptc_pass"];
const EPICENE: ReadonlySet<string> = new Set(
  "глава съдия колега слуга юноша будала пинтия владика войвода паша ага кадия дядо чичо вуйчо батко тате сираче пияница убиец левичар роднина".split(" "),
);

type Token = readonly [word: string, start: number, end: number];

const set = (words: string): ReadonlySet<string> => new Set(words.trim().split(/\s+/));

const genderExtra = once(() => {
  const out = new Map<string, string[]>();
  for (const line of dataText("gender_extra.tsv").split("\n")) {
    if (line.trim()) {
      const [base, genders] = line.split("\t");
      out.set(base, [...genders]);
    }
  }
  return out;
});

function genders(reading: Reading): Set<string | undefined> {
  const found = new Set<string | undefined>([reading.tag.g, ...(genderExtra().get(reading.base) ?? [])]);
  if (EPICENE.has(reading.base) || reading.base.endsWith("ица")) {
    found.add("m");
    found.add("f");
  }
  return found;
}

function readings(word: string): readonly Reading[] {
  return analyse(sub("^(?:най|по)-", "", word.toLowerCase()));
}

function isModifier(r: Reading): boolean {
  const tag = r.tag;
  return (
    MODIFIER_POS.has(tag.pos as string) ||
    (tag.pos === "V" && ATTRIBUTE_PARTICIPLES.includes(tag.v as string) && "n" in tag)
  );
}

function allModifiers(found: readonly Reading[]): boolean {
  return found.length > 0 && found.every(isModifier);
}

/** Whether every remaining reading is a common noun, and those readings: names and vocatives dropped. */
function allNouns(found: readonly Reading[], drop?: (r: Reading) => boolean): [boolean, Reading[]] {
  const kept = found.filter((r) => !("voc" in r.tag) && r.tag.pos !== "Np" && !drop?.(r));
  return [kept.length > 0 && kept.every((r) => r.tag.pos === "N"), kept];
}

function numberOf(r: Reading): string | undefined {
  return r.tag.n === "c" ? "p" : r.tag.n;
}

function agree(modifier: Reading, noun: Reading): boolean {
  if (numberOf(modifier) !== numberOf(noun)) return false;
  return numberOf(modifier) === "p" || genders(noun).has(modifier.tag.g);
}

function caseLike(fix: string, like: string): string {
  return isUpper(first(like)) ? upperFirst(fix) : fix;
}

function keepPrefix(word: string, fix: string): string {
  const m = match("^((?:най|по)-)", word, 0, "i");
  return m ? m.group(1) + fix : fix;
}

function sentenceStart(text: string, start: number): boolean {
  return search(String.raw`(^|[.!?…:;]\s*|[„\"«(]\s*|\n\s*)$`, before(text, start)) !== null;
}

/** A capital that does not start a sentence: a name or a title word. */
function isNameAt(text: string, word: string, start: number): boolean {
  return isUpper(first(word)) && !sentenceStart(text, start) && !match("(?:Ваш|Вие|Вас|Ви)", word);
}

/** The word at `i` is followed by a noun or a Latin word: it may be attributive. */
function attributive(text: string, tokens: readonly Token[], i: number): boolean {
  const end = tokens[i][2];
  const next = text.slice(end, end + 1);
  if (next === "/" || next === "-" || match(" [A-Za-z0-9◊]", text.slice(end, end + 2))) return true;
  if (i + 1 >= tokens.length || text.slice(end, tokens[i + 1][1]) !== " ") return false;
  const following = readings(tokens[i + 1][0]);
  return !following.length || following.some((r) => r.tag.pos === "N" || r.tag.pos === "A" || (isModifier(r) && !("clitic" in r.tag)));
}

const UNARTICLED_BASES: ReadonlySet<string> = new Set(["кръстопът"]);

function doubleArticle(text: string, tokens: readonly Token[]): Hit[] {
  const hits: Hit[] = [];
  for (let i = 0; i + 1 < tokens.length; i++) {
    const [w1, s1, e1] = tokens[i];
    const [w2, s2, e2] = tokens[i + 1];
    if (text.slice(e1, s2) !== " " || isUpper(first(w2)) || isNameAt(text, w1, s1)) continue;
    if (w1.toLowerCase() === "противното" || w1.toLowerCase() === "другото") continue;
    if (UNARTICLED_BASES.has(w2.toLowerCase())) continue;
    const firstWord = readings(w1);
    const [isNoun, second] = allNouns(readings(w2));
    if (!(allModifiers(firstWord) && isNoun)) continue;
    if (![...firstWord, ...second].every((r) => ["h", "f", "d"].includes(r.tag.d as string))) continue;
    if (!firstWord.some((a) => second.some((b) => agree(a, b)))) continue;
    const fixes = new Set<string>();
    for (const b of second) {
      const found = b.tag.n !== "s" || b.tag.g !== "m" ? inflect(b.lemma, { n: b.tag.n, d: "i" }) : inflect(b.lemma, { n: "s", d: "i" });
      for (const f of found) fixes.add(f);
    }
    hits.push({
      code: "double_article",
      start: s2,
      end: e2,
      message: "Only the first word of the phrase takes the article",
      fix: fixes.size === 1 ? ([...fixes][0] as string) : null,
    });
  }
  return hits;
}

const COPULA = set("е са беше бяха бъде бъдат остава става стана изглежда");
const TIME_WORDS = set(`понеделник вторник сряда четвъртък петък събота неделя ден месец час сезон уикенд
януари февруари март април май юни юли август септември октомври ноември декември`);

function articleAfterCopula(text: string, tokens: readonly Token[]): Hit[] {
  const hits: Hit[] = [];
  for (let i = 0; i + 1 < tokens.length; i++) {
    const [w1, s1, e1] = tokens[i];
    const [w2, s2, e2] = tokens[i + 1];
    if (!COPULA.has(w1.toLowerCase()) || text.slice(e1, s2) !== " " || isNameAt(text, w2, s2)) continue;
    if (
      i &&
      text.slice(tokens[i - 1][2], s1) === " " &&
      readings(tokens[i - 1][0]).some((r) => r.tag.v === "ptc_aor" || r.tag.v === "ptc_impf")
    ) {
      continue; // `Размътили са целия поток`: an auxiliary, the phrase is an object
    }
    if (i + 2 < tokens.length && TIME_WORDS.has(tokens[i + 2][0].toLowerCase())) continue;
    const found = readings(w2);
    if (!found.length || !found.every((r) => r.tag.d === "h" && r.tag.g === "m" && r.tag.n === "s" && isModifier(r))) continue;
    const fixes = new Set<string>();
    for (const r of found) {
      const want: Record<string, string | undefined> = { g: "m", n: "s", d: "f" };
      if ("v" in r.tag) want.v = r.tag.v;
      for (const f of inflect(r.lemma, want)) fixes.add(f);
    }
    hits.push({
      code: "article_after_copula",
      start: s2,
      end: e2,
      message: "After „е“ the masculine word takes the full article (-ят/-ът)",
      fix: fixes.size === 1 ? keepPrefix(w2, [...fixes][0] as string) : null,
    });
  }
  return hits;
}

const NUMBER_WORDS = set(`два три четири пет шест седем осем девет десет единадесет дванадесет тринадесет четиринадесет
петнадесет шестнадесет седемнадесет осемнадесет деветнадесет двадесет тридесет четиридесет петдесет
шестдесет седемдесет осемдесет деветдесет сто двеста триста няколко колко толкова`);
const PERSON_SUFFIX = "тел ник ач яч ист ант ент лог чия джия ьор ар яр ер ор ик ак як ок ец ин ан ян ич ит ат ед ен ах ех".split(" ");
const PERSONS = set(`кмет атлет член депутат министър гост пилот герой съсед грък чех фен монах цар крал принц граф бог
мъж син брат внук роб войн шеф експерт лидер човек юнак момък старец пророк апостол дякон поп свещеник лекар
доктор адвокат съдия прокурор инженер техник офицер генерал полковник капитан сержант редник воин рицар`);
const NOT_PERSONS = set("месец танец конец палец образец резервоар долар сантиметър километър");

/** May this masculine noun be a person? Then the plural is right after a numeral. */
function person(r: Reading): boolean {
  const base = r.base;
  if (PERSONS.has(base)) return true;
  if (NOT_PERSONS.has(base)) return false;
  for (const tag of forms(r.lemma).keys()) if (tag.includes("voc=1")) return true;
  return endsWithAny(base, PERSON_SUFFIX);
}

const COUNT_OF_PLURAL = new Map([["пътища", ["пътя"]]]);

function countAfter(text: string, end: number, following: readonly Token[]): Hit[] {
  let previous = end;
  for (const [word, start, stop] of following) {
    const gap = text.slice(previous, start);
    if ((gap !== " " && gap !== "\xa0") || isUpper(first(word))) return [];
    const found = readings(word);
    if (allModifiers(found) && found.every((r) => r.tag.n === "p" && r.tag.d === "i")) {
      previous = stop;
      continue; // `три нови телефони`: past the adjectives
    }
    const [isNoun, nouns] = allNouns(found);
    if (!isNoun || !nouns.every((r) => r.tag.g === "m" && r.tag.n === "p" && r.tag.d === "i")) return [];
    if (nouns.some(person)) return [];
    const counts =
      COUNT_OF_PLURAL.get(word.toLowerCase()) ??
      [...new Set(nouns.flatMap((r) => inflect(r.lemma, { n: "c" })))].sort();
    if (!counts.length || counts.includes(word.toLowerCase())) return [];
    return [
      {
        code: "count_form",
        start,
        end: stop,
        message: "After a number a masculine noun takes the count form",
        fix: counts.length === 1 ? counts[0] : null,
      },
    ];
  }
  return [];
}

function bisectRight(values: readonly number[], x: number): number {
  let low = 0;
  let high = values.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (x < values[middle]) high = middle;
    else low = middle + 1;
  }
  return low;
}

function countForm(text: string, tokens: readonly Token[]): Hit[] {
  const hits: Hit[] = [];
  const starts = tokens.map((t) => t[1]);
  for (const m of finditer(String.raw`(?<![\w.,/-])(\d+)(?=[ \xa0][А-Яа-я])`, text)) {
    const number = m.group(1);
    if (number.endsWith("1") && !number.endsWith("11")) continue; // `21 месец`: one takes the singular
    const previous = search(String.raw`(\S+)\s+$`, before(text, m.index));
    if (previous) {
      const word = previous.group(1);
      const found = readings(word);
      if (
        endsWithAny(word, [".", "№", "/"]) ||
        fullmatch(String.raw`[A-Za-z][\w-]*`, word) ||
        (found.length > 0 && found.every((r) => r.tag.pos === "N" || r.tag.pos === "Nm"))
      ) {
        continue; // `член 68 органите`, `NUTS 2`: a reference, not a count
      }
    }
    if (search(String.raw`\d\s*(?:,|и|или)\s*$`, before(text, m.index))) continue; // a list of references
    const following = bisectRight(starts, m.end);
    hits.push(...countAfter(text, m.end, tokens.slice(following, following + 3)));
  }
  tokens.forEach(([word, , stop], i) => {
    if (NUMBER_WORDS.has(word.toLowerCase())) hits.push(...countAfter(text, stop, tokens.slice(i + 1, i + 4)));
  });
  return hits;
}

/** Masculine nouns that name only people: after a number the plural, `5 служители`. */
const PERSON_NOUNS = set(`служител ученик студент учител преподавател лекар клиент потребител ползвател абонат
работник специалист експерт консултант гост пасажер депутат кмет министър войник
полицай пациент жител посетител зрител читател слушател турист спортист играч състезател
треньор сътрудник колега приятел съученик съсед гражданин стажант докторант първокласник
абсолвент възпитаник победител финалист доброволец дарител инвеститор акционер собственик
наемател купувач продавач търговец шофьор пилот моряк офицер генерал журналист адвокат
прокурор съдия инженер програмист мениджър директор чиновник представител наблюдател делегат
избирател привърженик поддръжник пенсионер футболист баскетболист волейболист тенисист
боксьор атлет шампион медалист лауреат автор писател художник музикант артист актьор певец
танцьор фотограф хирург фармацевт стоматолог медик санитар болногледач брокер счетоводител
юрист икономист библиотекар готвач сервитьор барман фермер строител монтьор механик шивач
фризьор пощальон куриер охранител пазач затворник бежанец мигрант емигрант имигрант арестант
извършител крадец убиец свидетел заложник младеж мъж син брат внук братовчед племенник
съпруг годеник`);
const PERSON_COUNTERS: ReadonlySet<string> = new Set([...NUMBER_WORDS].filter((w) => w !== "два" && w !== "три" && w !== "четири"));

function personCount(text: string, end: number, following: readonly Token[]): Hit[] {
  let previous = end;
  for (const [word, start, stop] of following) {
    const gap = text.slice(previous, start);
    if ((gap !== " " && gap !== "\xa0") || isUpper(first(word))) return [];
    const found = readings(word);
    if (allModifiers(found) && found.every((r) => r.tag.n === "p" && r.tag.d === "i")) {
      previous = stop;
      continue; // `5 нови служителя`: past the adjectives
    }
    const [isNoun, nouns] = allNouns(found);
    if (
      !isNoun ||
      !nouns.every((r) => PERSON_NOUNS.has(r.base) && r.tag.g === "m" && (r.tag.n === "c" || (r.tag.n === "s" && r.tag.d === "h")))
    ) {
      return [];
    }
    const plurals = [...new Set(nouns.flatMap((r) => inflect(r.lemma, { n: "p", d: "i" })))].sort();
    if (!plurals.length) return [];
    return [
      {
        code: "count_form_person",
        start,
        end: stop,
        message: "After a number a noun naming people takes the plural",
        fix: plurals.length === 1 ? plurals[0] : null,
      },
    ];
  }
  return [];
}

function countFormPerson(text: string, tokens: readonly Token[]): Hit[] {
  const hits: Hit[] = [];
  const starts = tokens.map((t) => t[1]);
  for (const m of finditer(String.raw`(?<![\w.,/:-])(\d+)(?=[ \xa0][а-я])`, text)) {
    const number = m.group(1);
    if (number.endsWith("1") && !number.endsWith("11")) continue; // `21 служител`
    if (search(String.raw`(?:[.№/:-]|[A-Za-z][\w-]*|\d\s*(?:,|и|или))\s*$`, before(text, m.index))) continue;
    if (fullmatch(String.raw`(?:19|20)\d\d`, number) && search(String.raw`(?<![\w-])(?:от|през|в|до|след|преди)\s+$`, before(text, m.index).toLowerCase())) {
      continue; // a year
    }
    const previous = search(String.raw`(\S+)\s+$`, before(text, m.index));
    const previousReadings = previous ? readings(previous.group(1)) : [];
    if (previousReadings.length && previousReadings.every((r) => r.tag.pos === "N" || r.tag.pos === "Nm")) continue;
    const following = bisectRight(starts, m.end);
    hits.push(...personCount(text, m.end, tokens.slice(following, following + 3)));
  }
  tokens.forEach(([word, , stop], i) => {
    if (PERSON_COUNTERS.has(word.toLowerCase())) hits.push(...personCount(text, stop, tokens.slice(i + 1, i + 4)));
  });
  return hits;
}

const PERSONAL_NUMERALS = set("двама трима четирима петима шестима седмина осмина деветима десетима");

function pluralAfterDvama(text: string, tokens: readonly Token[]): Hit[] {
  const hits: Hit[] = [];
  for (let i = 0; i + 1 < tokens.length; i++) {
    const [w1, , e1] = tokens[i];
    const [w2, s2, e2] = tokens[i + 1];
    const numeral = w1.toLowerCase();
    if (!PERSONAL_NUMERALS.has(numeral) || text.slice(e1, s2) !== " " || isUpper(first(w2))) continue;
    const [isNoun, nouns] = allNouns(readings(w2), (r) => r.tag.pos === "V" && r.tag.n === "s");
    if (!isNoun || attributive(text, tokens, i + 1) || w2.toLowerCase() === "човека") continue;
    if (
      nouns.every((r) => r.tag.g === "m" && (r.tag.n === "c" || (r.tag.n === "s" && r.tag.d === "h"))) &&
      nouns.some((r) => r.tag.n === "c")
    ) {
      const plurals = [...new Set(nouns.flatMap((r) => inflect(r.lemma, { n: "p", d: "i" })))].sort();
      hits.push({
        code: "plural_after_dvama",
        start: s2,
        end: e2,
        message: `After „${numeral}“ use the plural, not the count form`,
        fix: plurals.length === 1 ? plurals[0] : null,
      });
    }
  }
  return hits;
}

const IMPERSONAL = set("трябва може има няма струва следва предстои важи личи стига ще би бих бихме бихте биха е");

function vieAgreement(text: string, tokens: readonly Token[]): Hit[] {
  const hits: Hit[] = [];
  for (let i = 0; i + 1 < tokens.length; i++) {
    const [w1, s1, e1] = tokens[i];
    const [w2, s2, e2] = tokens[i + 1];
    if (w1.toLowerCase() !== "вие" || text.slice(e1, s2) !== " ") continue;
    const found = readings(w2);
    if (
      IMPERSONAL.has(w2.toLowerCase()) ||
      !found.length ||
      !found.every((r) => r.tag.pos === "V" && ["pres", "aor", "impf"].includes(r.tag.v as string) && "p" in r.tag)
    ) {
      continue;
    }
    if (search(String.raw`(?:\bи|,)\s+$`, before(text, s1))) continue; // `трима другари и вие`
    if (found.some((r) => r.tag.p === "2" && r.tag.n === "p")) continue;
    let fix: string | null = null;
    for (const tense of ["pres", "aor", "impf"]) {
      const fixes = new Set(found.filter((r) => r.tag.v === tense).flatMap((r) => inflect(r.lemma, { v: tense, p: "2", n: "p" })));
      if (fixes.size) {
        fix = fixes.size === 1 ? caseLike([...fixes][0], w2) : null;
        break;
      }
    }
    hits.push({ code: "vie_agreement", start: s2, end: e2, message: "The verb agrees with „Вие“: 2nd person plural", fix });
  }
  return hits;
}

const VIE_AUXILIARIES = set("сте бяхте бихте");
const CLITICS = set("се си ми ти му ѝ й ни ви им го я ги");

/** `Вие сте казал` → `казали`: with `Вие` the л-participle is plural; adjectives and passive participles are left alone. */
function vieParticiple(text: string, tokens: readonly Token[]): Hit[] {
  const hits: Hit[] = [];
  for (let i = 0; i + 2 < tokens.length; i++) {
    const [w1, s1, e1] = tokens[i];
    const [aux, sa, ea] = tokens[i + 1];
    if (w1.toLowerCase() !== "вие" || text.slice(e1, sa) !== " ") continue;
    if (search(String.raw`(?:\bи|,)\s+$`, before(text, s1))) continue; // a coordinated subject
    let j = i + 1;
    if (aux.toLowerCase() === "не" && j + 1 < tokens.length && text.slice(ea, tokens[j + 1][1]) === " ") j += 1;
    if (!VIE_AUXILIARIES.has(tokens[j][0].toLowerCase())) continue;
    j += 1;
    while (j < tokens.length && CLITICS.has(tokens[j][0].toLowerCase()) && text.slice(tokens[j - 1][2], tokens[j][1]) === " ") j += 1;
    if (j >= tokens.length || text.slice(tokens[j - 1][2], tokens[j][1]) !== " ") continue;
    const [word, start, stop] = tokens[j];
    const found = readings(word);
    if (!found.length || !found.every((r) => r.tag.pos === "V" && (r.tag.v === "ptc_aor" || r.tag.v === "ptc_impf") && r.tag.n === "s")) {
      continue;
    }
    const plurals = [...new Set(found.flatMap((r) => inflect(r.lemma, { v: r.tag.v, n: "p", d: "i" })))].sort();
    hits.push({
      code: "vie_agreement",
      start,
      end: stop,
      message: "With „Вие“ the participle is plural",
      fix: plurals.length === 1 ? caseLike(plurals[0], word) : null,
    });
  }
  return hits;
}

const DETECTORS = [doubleArticle, articleAfterCopula, countForm, countFormPerson, pluralAfterDvama, vieAgreement, vieParticiple];

/** The agreement rules of one text; offsets are into `text`. */
export function check(text: string): Hit[] {
  const normal = normalise(text);
  const tokens = finditer(WORD, normal).map((m): Token => [m.group(0), m.index, m.end]);
  const unique = new Map<string, Hit>();
  for (const detector of DETECTORS) {
    for (const found of detector(normal, tokens)) {
      if (normal.slice(found.start, found.end).includes("◊")) continue;
      const hit = found.fix === null || normal.slice(found.start, found.end) === text.slice(found.start, found.end) ? found : { ...found, fix: null };
      unique.set(JSON.stringify([hit.code, hit.start, hit.end, hit.message, hit.fix]), hit);
    }
  }
  return byPosition([...unique.values()]);
}
