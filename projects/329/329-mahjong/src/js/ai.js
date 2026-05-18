// ========== AI 逻辑 ==========
class MahjongAI {
  // 选择出哪张牌
  static chooseDiscard(hand, melds) {
    // 策略: 打孤张 > 打风牌 > 打边张
    const counts = countTiles(hand);
    let bestTile = null;
    let bestScore = Infinity;

    for (const t of hand) {
      const score = MahjongAI.tileValue(t, counts, hand);
      if (score < bestScore) {
        bestScore = score;
        bestTile = t;
      }
    }
    return bestTile || hand[hand.length - 1];
  }

  static tileValue(tile, counts, hand) {
    const k = tileKey(tile);
    const c = counts[k] || 0;
    let score = 0;

    // 对子+10, 刻子+30
    if (c >= 3) score += 30;
    else if (c >= 2) score += 10;

    // 数牌的连接性
    if (['wan','tiao','tong'].includes(tile.suit)) {
      const v = tile.value;
      const has = (val) => hand.some(t => t.suit === tile.suit && t.value === val);
      // 有相邻牌
      if (has(v - 1)) score += 8;
      if (has(v + 1)) score += 8;
      if (has(v - 2)) score += 3;
      if (has(v + 2)) score += 3;
      // 中间张更有价值
      if (v >= 3 && v <= 7) score += 2;
    } else {
      // 风牌/箭牌 孤张价值低
      if (c === 1) score -= 5;
    }
    return score;
  }

  // AI决定是否碰/杠/吃/胡
  static decideAction(actions, hand, melds) {
    // 优先级：胡 > 杠 > 碰 > 吃
    if (actions.hu) return 'hu';
    if (actions.gang) return 'gang';
    if (actions.peng) {
      // 碰的策略: 评估碰了之后是否更好
      return 'peng';
    }
    if (actions.chi) {
      // 吃的策略简单: 有就吃(66%概率)
      return Math.random() < 0.66 ? 'chi' : 'pass';
    }
    return 'pass';
  }

  // 自摸后AI决策
  static decideSelfAction(actions) {
    if (actions.hu) return 'hu';
    if (actions.angang && actions.angang.length > 0) return { type:'angang', key:actions.angang[0] };
    if (actions.jiagang && actions.jiagang.length > 0) return { type:'jiagang', key:actions.jiagang[0] };
    return 'discard';
  }
}
