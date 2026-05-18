// ========== 牌定义 ==========
const SUITS = {
  wan:  { name:'万', nums:['一','二','三','四','五','六','七','八','九'] },
  tiao: { name:'条', nums:['一','二','三','四','五','六','七','八','九'] },
  tong: { name:'筒', nums:['①','②','③','④','⑤','⑥','⑦','⑧','⑨'] },
};
const FENG_VALUES = ['dong','nan','xi','bei'];
const FENG_NAMES = { dong:'东', nan:'南', xi:'西', bei:'北' };
const JIAN_VALUES = ['zhong','fa','bai'];
const JIAN_NAMES = { zhong:'中', fa:'發', bai:'白' };

// 牌 ID: suit-value, e.g. "wan-1", "feng-dong", "jian-zhong"
function createFullDeck() {
  const deck = [];
  // 万条筒 各 1-9，每种4张
  for (const suit of ['wan','tiao','tong']) {
    for (let v = 1; v <= 9; v++) {
      for (let i = 0; i < 4; i++) {
        deck.push({ suit, value: v, id: `${suit}-${v}-${i}` });
      }
    }
  }
  // 风牌
  for (const v of FENG_VALUES) {
    for (let i = 0; i < 4; i++) {
      deck.push({ suit:'feng', value: v, id: `feng-${v}-${i}` });
    }
  }
  // 箭牌
  for (const v of JIAN_VALUES) {
    for (let i = 0; i < 4; i++) {
      deck.push({ suit:'jian', value: v, id: `jian-${v}-${i}` });
    }
  }
  return deck; // 136 张
}

function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function tileKey(t) { return `${t.suit}-${t.value}`; }

function tileName(t) {
  if (t.suit === 'feng') return FENG_NAMES[t.value];
  if (t.suit === 'jian') return JIAN_NAMES[t.value];
  return SUITS[t.suit].nums[t.value - 1] + SUITS[t.suit].name;
}

function tileDisplay(t) {
  if (t.suit === 'feng') return { num: FENG_NAMES[t.value], suitLabel: '' };
  if (t.suit === 'jian') return { num: JIAN_NAMES[t.value], suitLabel: '' };
  return { num: SUITS[t.suit].nums[t.value - 1], suitLabel: SUITS[t.suit].name };
}

function tileSort(a, b) {
  const order = { wan:0, tiao:1, tong:2, feng:3, jian:4 };
  if (order[a.suit] !== order[b.suit]) return order[a.suit] - order[b.suit];
  const va = typeof a.value === 'number' ? a.value : FENG_VALUES.indexOf(a.value) * 10 + JIAN_VALUES.indexOf(a.value);
  const vb = typeof b.value === 'number' ? b.value : FENG_VALUES.indexOf(b.value) * 10 + JIAN_VALUES.indexOf(b.value);
  return va - vb;
}

// 统计手牌中各种牌的数量
function countTiles(hand) {
  const counts = {};
  for (const t of hand) {
    const k = tileKey(t);
    counts[k] = (counts[k] || 0) + 1;
  }
  return counts;
}

// ========== 胡牌判断 ==========
function canHu(hand) {
  // 标准: 4面子(顺子或刻子) + 1雀头 = 14张
  if (hand.length !== 14) return false;
  const counts = countTiles(hand);
  return checkHu(counts);
}

function checkHu(counts) {
  // 尝试每种牌做雀头
  for (const key of Object.keys(counts)) {
    if (counts[key] >= 2) {
      counts[key] -= 2;
      if (checkMelds(counts, 4)) { counts[key] += 2; return true; }
      counts[key] += 2;
    }
  }
  return false;
}

function checkMelds(counts, needed) {
  if (needed === 0) {
    return Object.values(counts).every(c => c === 0);
  }
  // 找第一个非零的牌
  for (const key of Object.keys(counts)) {
    if (counts[key] <= 0) continue;
    // 尝试刻子
    if (counts[key] >= 3) {
      counts[key] -= 3;
      if (checkMelds(counts, needed - 1)) { counts[key] += 3; return true; }
      counts[key] += 3;
    }
    // 尝试顺子(只有万条筒)
    const [suit, valStr] = key.split('-');
    const val = parseInt(valStr);
    if (['wan','tiao','tong'].includes(suit) && !isNaN(val) && val <= 7) {
      const k2 = `${suit}-${val+1}`, k3 = `${suit}-${val+2}`;
      if ((counts[k2]||0) >= 1 && (counts[k3]||0) >= 1) {
        counts[key]--; counts[k2]--; counts[k3]--;
        if (checkMelds(counts, needed - 1)) { counts[key]++; counts[k2]++; counts[k3]++; return true; }
        counts[key]++; counts[k2]++; counts[k3]++;
      }
    }
    return false; // 第一张非零牌必须被消耗掉
  }
  return needed === 0;
}

// ========== 碰/杠/吃判断  ==========
function canPeng(hand, tile) {
  let c = 0;
  for (const t of hand) if (tileKey(t) === tileKey(tile)) c++;
  return c >= 2;
}

function canGang(hand, tile) {
  let c = 0;
  for (const t of hand) if (tileKey(t) === tileKey(tile)) c++;
  return c >= 3;
}

function canAnGang(hand) {
  // 暗杠: 手中4张相同
  const counts = countTiles(hand);
  const result = [];
  for (const [key, count] of Object.entries(counts)) {
    if (count === 4) result.push(key);
  }
  return result;
}

function canJiaGang(hand, melds) {
  // 加杠: 手中有一张牌和碰出的刻子相同
  const result = [];
  for (const meld of melds) {
    if (meld.type === 'peng') {
      const k = tileKey(meld.tiles[0]);
      if (hand.some(t => tileKey(t) === k)) result.push(k);
    }
  }
  return result;
}

function canChi(hand, tile, playerIdx, discardPlayerIdx) {
  // 只有上家打的牌才能吃
  if ((discardPlayerIdx + 1) % 4 !== playerIdx) return [];
  if (!['wan','tiao','tong'].includes(tile.suit)) return [];
  const v = tile.value;
  const results = [];
  const has = (val) => hand.some(t => t.suit === tile.suit && t.value === val);
  // v-2, v-1, v
  if (v >= 3 && has(v-2) && has(v-1)) results.push([v-2, v-1, v]);
  // v-1, v, v+1
  if (v >= 2 && v <= 8 && has(v-1) && has(v+1)) results.push([v-1, v, v+1]);
  // v, v+1, v+2
  if (v <= 7 && has(v+1) && has(v+2)) results.push([v, v+1, v+2]);
  return results;
}

// 听牌判断: 加一张牌后能胡
function getTingTiles(hand) {
  const result = [];
  const allPossible = new Set();
  for (const suit of ['wan','tiao','tong']) {
    for (let v = 1; v <= 9; v++) allPossible.add(`${suit}-${v}`);
  }
  for (const v of FENG_VALUES) allPossible.add(`feng-${v}`);
  for (const v of JIAN_VALUES) allPossible.add(`jian-${v}`);

  for (const key of allPossible) {
    const [suit, value] = key.split('-');
    const fakeTile = { suit, value: isNaN(parseInt(value)) ? value : parseInt(value) };
    const testHand = [...hand, fakeTile];
    if (canHu(testHand)) result.push(fakeTile);
  }
  return result;
}
