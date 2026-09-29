// On-screen language: English by default, Japanese on request (?lang=ja, or the button at the top right).
// The choice is remembered in this browser. Static text in index.html carries data-t="key"; dynamic text asks t().
const S = {
  en: {
    title: 'Shiomachi', titleSub: 'a bezaisen on the Seto Inland Sea', cardSub: 'Waiting for the Tide',
    goal: 'Leave Ōshima Harbour at dawn and thread the islands to Mukaijima Harbour.<br>Read the dark bands of wind and the run of the tide, and drop anchor before nightfall.',
    go: 'Set sail', loading: 'Loading',
    hint: 'W raises the sail, A / D steer. Leave the sail to the master, or trim it yourself with Q / E.',
    knots: 'knots', aw: 'apparent wind (felt on board)',
    keys: '<kbd>A</kbd><kbd>D</kbd> helm　<kbd>W</kbd><kbd>S</kbd> raise / lower sail　<kbd>Q</kbd><kbd>E</kbd> trim　<kbd>T</kbd> master trims　<kbd>R</kbd> scull　<kbd>Space</kbd> anchor　<kbd>C</kbd> view',
    anchored: 'At anchor', trimAuto: 'The master trims the sail', trimHand: 'Trimming by hand',
    dirs: ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
    dirs16: ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'],
    wind: (d, s) => `${d} wind ${s} m/s`,
    time: (h, m) => `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`,
    dest: (n, km) => `${n}  ${km} km`,
    slack: 'Slack water', flood: 'Flood tide (running east)', ebb: 'Ebb tide (running west)',
    anchorDown: 'Anchor down', anchorUp: 'Anchor up', anchorHint: 'In the harbour, press Space to anchor',
    depart: (a, b) => `${a}\nbound for ${b}`,
    arrive: (n, h, m, km, th, tm) => `Arrived at ${n}\n${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}   ${km} km in ${th} h ${tm} min`,
    ports: { '大島の浦': 'Ōshima Harbour', '向島の浦': 'Mukaijima Harbour' },
    lang: '日本語',
  },
  ja: {
    title: '潮待ち', titleSub: '弁才船・瀬戸内', cardSub: '弁才船で瀬戸内を渡る',
    goal: '朝の大島の浦から、島々のあいだを抜けて向島の浦へ。<br>風の帯と潮を読み、日が暮れる前に錨を入れる。',
    go: '舟を出す', loading: '読み込み中',
    hint: 'W で帆を上げ、A・D で舵。帆の向きは船頭にまかせても、Q・E で自分で合わせてもいい。',
    knots: 'ノット', aw: '見かけの風（船から感じる風）',
    keys: '<kbd>A</kbd><kbd>D</kbd> 舵　<kbd>W</kbd><kbd>S</kbd> 帆を上げ下げ　<kbd>Q</kbd><kbd>E</kbd> 帆の向き　<kbd>T</kbd> 船頭まかせ　<kbd>R</kbd> 櫓　<kbd>Space</kbd> 錨　<kbd>C</kbd> 視点',
    anchored: '錨泊中', trimAuto: '船頭まかせ', trimHand: '手で帆を合わせる',
    dirs: ['北', '北東', '東', '南東', '南', '南西', '西', '北西'],
    dirs16: ['北', '北北東', '北東', '東北東', '東', '東南東', '南東', '南南東', '南', '南南西', '南西', '西南西', '西', '西北西', '北西', '北北西'],
    wind: (d, s) => `${d}の風 ${s}m`,
    time: (h, m) => `${h}時${String(m).padStart(2, '0')}分`,
    dest: (n, km) => `${n}まで ${km}km`,
    slack: '潮どまり', flood: '上げ潮（東へ流れる）', ebb: '下げ潮（西へ流れる）',
    anchorDown: '錨を入れた', anchorUp: '錨を上げた', anchorHint: '港に入ったら Space で錨を入れる',
    depart: (a, b) => `${a}\n${b}へ`,
    arrive: (n, h, m, km, th, tm) => `${n}に着いた\n${h}時${String(m).padStart(2, '0')}分　${km}km を ${th}時間${tm}分`,
    ports: {},
    lang: 'English',
  },
};

function initial() {
  const q = new URLSearchParams(location.search).get('lang');
  if (q === 'ja' || q === 'en') return q;
  try { const v = localStorage.getItem('shiomachi.lang'); if (v === 'ja' || v === 'en') return v; } catch (e) { /* storage blocked */ }
  return 'en';
}

let lang = initial();
const listeners = [];
export const t = (k) => S[lang][k];
export const place = (name) => S[lang].ports[name] ?? name;
export const getLang = () => lang;
export function onLang(fn) { listeners.push(fn); }
export function applyStatic() {
  document.documentElement.lang = lang;
  for (const el of document.querySelectorAll('[data-t]')) el.innerHTML = t(el.dataset.t);
  for (const el of document.querySelectorAll('[data-t-title]')) el.title = t(el.dataset.tTitle);
}
export function setLang(l) {
  lang = l;
  try { localStorage.setItem('shiomachi.lang', l); } catch (e) { /* storage blocked */ }
  applyStatic();
  listeners.forEach((fn) => fn(l));
}
export function toggleLang() { setLang(lang === 'en' ? 'ja' : 'en'); }
