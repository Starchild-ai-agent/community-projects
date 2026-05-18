// ========== 游戏核心 ==========
class MahjongGame {
  constructor() {
    this.reset();
  }

  reset() {
    this.wall = shuffle(createFullDeck());
    this.players = [
      { hand:[], melds:[], discards:[], seat:'dong', name:'东(AI)' },
      { hand:[], melds:[], discards:[], seat:'nan', name:'南(你)' },
      { hand:[], melds:[], discards:[], seat:'xi',  name:'西(AI)' },
      { hand:[], melds:[], discards:[], seat:'bei', name:'北(AI)' },
    ];
    this.humanIdx = 1;
    this.currentIdx = 0; // 东家先摸
    this.phase = 'idle'; // idle | draw | discard | action | end
    this.lastDiscard = null;
    this.lastDiscardIdx = -1;
    this.actionQueue = [];
    this.pendingActions = {};
    this.gameOver = false;
  }

  deal() {
    // 每人13张
    for (let round = 0; round < 13; round++) {
      for (let p = 0; p < 4; p++) {
        this.players[p].hand.push(this.wall.pop());
      }
    }
    // 排序
    for (const p of this.players) p.hand.sort(tileSort);
    this.phase = 'draw';
  }

  get tilesLeft() { return this.wall.length; }
  get currentPlayer() { return this.players[this.currentIdx]; }

  // 摸牌
  draw(playerIdx) {
    if (this.wall.length === 0) {
      this.endGame(null, 'draw'); // 流局
      return null;
    }
    const tile = this.wall.pop();
    this.players[playerIdx].hand.push(tile);
    this.phase = 'discard';
    return tile;
  }

  // 出牌
  discard(playerIdx, tileId) {
    const p = this.players[playerIdx];
    const idx = p.hand.findIndex(t => t.id === tileId);
    if (idx === -1) return null;
    const tile = p.hand.splice(idx, 1)[0];
    p.discards.push(tile);
    p.hand.sort(tileSort);
    this.lastDiscard = tile;
    this.lastDiscardIdx = playerIdx;
    return tile;
  }

  // 碰
  doPeng(playerIdx, tile) {
    const p = this.players[playerIdx];
    const matched = [];
    const remaining = [];
    for (const t of p.hand) {
      if (tileKey(t) === tileKey(tile) && matched.length < 2) matched.push(t);
      else remaining.push(t);
    }
    p.hand = remaining;
    p.melds.push({ type:'peng', tiles:[...matched, tile], from:this.lastDiscardIdx });
    // 从上家弃牌堆移除
    const dp = this.players[this.lastDiscardIdx];
    dp.discards = dp.discards.filter(t => t.id !== tile.id);
    p.hand.sort(tileSort);
    this.currentIdx = playerIdx;
    this.lastDiscard = null;
    this.phase = 'discard';
  }

  // 明杠(别人打的牌)
  doGang(playerIdx, tile) {
    const p = this.players[playerIdx];
    const matched = [];
    const remaining = [];
    for (const t of p.hand) {
      if (tileKey(t) === tileKey(tile) && matched.length < 3) matched.push(t);
      else remaining.push(t);
    }
    p.hand = remaining;
    p.melds.push({ type:'gang', tiles:[...matched, tile], from:this.lastDiscardIdx });
    const dp = this.players[this.lastDiscardIdx];
    dp.discards = dp.discards.filter(t => t.id !== tile.id);
    p.hand.sort(tileSort);
    this.currentIdx = playerIdx;
    this.lastDiscard = null;
    // 杠后补牌
    this.phase = 'draw';
    return this.draw(playerIdx);
  }

  // 暗杠
  doAnGang(playerIdx, tileKeyStr) {
    const p = this.players[playerIdx];
    const matched = [];
    const remaining = [];
    for (const t of p.hand) {
      if (tileKey(t) === tileKeyStr && matched.length < 4) matched.push(t);
      else remaining.push(t);
    }
    p.hand = remaining;
    p.melds.push({ type:'angang', tiles:matched, from:playerIdx });
    p.hand.sort(tileSort);
    this.phase = 'draw';
    return this.draw(playerIdx);
  }

  // 加杠
  doJiaGang(playerIdx, tileKeyStr) {
    const p = this.players[playerIdx];
    const tileIdx = p.hand.findIndex(t => tileKey(t) === tileKeyStr);
    if (tileIdx === -1) return null;
    const tile = p.hand.splice(tileIdx, 1)[0];
    // 找到碰的meld升级
    const meld = p.melds.find(m => m.type === 'peng' && tileKey(m.tiles[0]) === tileKeyStr);
    if (meld) {
      meld.type = 'gang';
      meld.tiles.push(tile);
    }
    p.hand.sort(tileSort);
    this.phase = 'draw';
    return this.draw(playerIdx);
  }

  // 吃
  doChi(playerIdx, tile, values) {
    const p = this.players[playerIdx];
    const usedTiles = [tile];
    const remaining = [...p.hand];
    for (const v of values) {
      if (v === tile.value) continue;
      const idx = remaining.findIndex(t => t.suit === tile.suit && t.value === v);
      if (idx !== -1) {
        usedTiles.push(remaining.splice(idx, 1)[0]);
      }
    }
    usedTiles.sort(tileSort);
    p.hand = remaining;
    p.melds.push({ type:'chi', tiles:usedTiles, from:this.lastDiscardIdx });
    const dp = this.players[this.lastDiscardIdx];
    dp.discards = dp.discards.filter(t => t.id !== tile.id);
    p.hand.sort(tileSort);
    this.currentIdx = playerIdx;
    this.lastDiscard = null;
    this.phase = 'discard';
  }

  // 胡
  doHu(playerIdx, tile, isSelfDraw) {
    this.endGame(playerIdx, isSelfDraw ? 'zimo' : 'hu', tile);
  }

  // 下一个玩家
  nextPlayer() {
    this.currentIdx = (this.currentIdx + 1) % 4;
  }

  // 结束
  endGame(winnerIdx, type, tile) {
    this.gameOver = true;
    this.phase = 'end';
    this.winner = winnerIdx;
    this.winType = type;
    this.winTile = tile;
  }

  // 检测其他玩家是否可以对最后一张弃牌行动
  checkActions(discardTile, discardIdx) {
    const actions = {};
    for (let i = 0; i < 4; i++) {
      if (i === discardIdx) continue;
      const p = this.players[i];
      const a = {};
      // 胡
      const testHand = [...p.hand, discardTile];
      if (canHu(testHand)) a.hu = true;
      // 杠
      if (canGang(p.hand, discardTile)) a.gang = true;
      // 碰
      if (canPeng(p.hand, discardTile)) a.peng = true;
      // 吃(下家)
      const chiOptions = canChi(p.hand, discardTile, i, discardIdx);
      if (chiOptions.length > 0) a.chi = chiOptions;
      if (Object.keys(a).length > 0) actions[i] = a;
    }
    return actions;
  }

  // 自摸后检查(暗杠/加杠/自摸胡)
  checkSelfActions(playerIdx) {
    const p = this.players[playerIdx];
    const a = {};
    if (canHu(p.hand)) a.hu = true;
    const ag = canAnGang(p.hand);
    if (ag.length > 0) a.angang = ag;
    const jg = canJiaGang(p.hand, p.melds);
    if (jg.length > 0) a.jiagang = jg;
    return a;
  }
}
