// Ruby alignment check for anki_back_template.html: node test_pinyin_align.js
// ponytail: runs the template's real script under a stub DOM, no test framework.
const fs = require('fs');
const assert = require('assert');

const script = fs.readFileSync(__dirname + '/anki_back_template.html', 'utf8')
  .match(/<script>([\s\S]*)<\/script>/)[1];

function render(hanzi, pinyin, segmented, mode) {
  let html = '';
  const el = { set innerHTML(v) { html = v; }, get innerHTML() { return html; } };
  const body = script
    .replace('"{{simplified}}"', JSON.stringify(hanzi))
    .replace('"{{pinyin}}"', JSON.stringify(pinyin))
    .replace('"{{pinyin_segmented}}"', JSON.stringify(segmented));
  new Function('document', 'localStorage', body)(
    { getElementById: (id) => (id === 'hanzi-ruby' ? el : null) },
    { getItem: () => mode, setItem: () => {} }
  );
  return html;
}

// [rb, rt] pairs emitted, in order.
function pairs(html) {
  return [...html.matchAll(/<rb>(.*?)<\/rb><rt>(.*?)<\/rt>/g)].map((m) => [m[1], m[2]]);
}

// [hanzi, pinyin, expected first rt, jieba segmentation as etl.common.segment_hanzi emits it]
const CASES = [
  // Q/A prefixes: "Q:" must be consumed as a latin token, not eaten by 你.
  ['Q: 你吃过中国菜吗？', 'Q: nǐ chī guò zhōng guó cài ma', 'nǐ', 'Q|:| |你|吃|过|中国|菜|吗|？'],
  ['Q1: 你会说中文吗？', 'Q1：nǐ huì shuō zhōng wén ma ？', 'nǐ', 'Q1|:| |你|会|说|中文|吗|？'],
  ['A: 没吃过。', 'A: méi chī guò', 'méi chī guò', 'A|:| |没吃过|。'],
  // Mid-sentence punctuation must not consume a syllable slot.
  ['对不起。我没有水。', 'duì bu qǐ 。 wǒ méi yǒu shuǐ 。', 'duì bu qǐ', '对不起|。|我|没有|水|。'],
  // Apostrophe inside a latin word.
  ['What’s up 是什么意思？', 'What’s up shì shén me yì si', 'shì', 'What|’|s| |up| |是|什么|意思|？'],
];

for (const [hanzi, pinyin, firstRt, segmented] of CASES) {
  for (const mode of ['singular', 'grouped']) {
    const p = pairs(render(hanzi, pinyin, segmented, mode));
    const want = mode === 'singular' ? firstRt.split(' ')[0] : firstRt;
    assert.ok(p.length, `${mode}: no ruby for ${hanzi}`);
    assert.strictEqual(p[0][1], want, `${mode}: ${hanzi} -> ${JSON.stringify(p)}`);
    assert.ok(p.every(([, rt]) => rt), `${mode}: empty pinyin in ${JSON.stringify(p)}`);
  }
}

// Erhua: 一点儿 / yì diǎn(r) must fill all three characters.
assert.deepStrictEqual(
  pairs(render('一点儿', 'yì diǎn(r)', '一|点|儿', 'singular')),
  [['一', 'yì'], ['点', 'diǎn'], ['儿', 'r']]
);

console.log('ok');
