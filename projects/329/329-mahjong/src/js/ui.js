// ========== UI 渲染 ==========
const PLAYER_MAP = { 0:'right', 1:'bottom', 2:'left', 3:'top' };
const SEAT_NAMES = { dong:'东', nan:'南', xi:'西', bei:'北' };

class MahjongUI {
  constructor() {
    this.selectedTileId = null;
    this.onDiscardCb = null;
    this.onActionCb = null;
  }

  // ---------- 牌元素 ----------
  createTileEl(tile, opts = {}) {
    const el = document.createElement('div');
    const d = tileDisplay(tile);
    el.className = 'tile suit-' + tile.suit;
    if (opts.small) el.classList.add('tile-small');
    if (opts.drawn) el.classList.add('drawn-tile');
    if (opts.lastDiscard) el.classList.add('last-discard');
    el.dataset.id = tile.id;
    el.dataset.value = tile.value;
    el.innerHTML = `<span class="tile-num">${d.num}</span>${d.suitLabel ? '<span class="tile-suit">' + d.suitLabel + '</span>' : ''}`;
    if (opts.clickable) {
      el.addEventListener('click', () => this._onTileClick(tile));
    }
    return el;
  }

  createTileBack(horizontal) {
    const el = document.createElement('div');
    el.className = horizontal ? 'tile-back-h' : 'tile-back';
    return el;
  }

  // ---------- 渲染全部 ----------
  renderAll(game) {
    for (let i = 0; i < 4; i++) {
      this.renderHand(game, i);
      this.renderDiscards(game, i);
      this.renderMelds(game, i);
    }
    this.renderInfo(game);
  }

  // ---------- 手牌 ----------
  renderHand(game, idx) {
    const pos = PLAYER_MAP[idx];
    const container = document.getElementById('hand-' + pos);
    container.innerHTML = '';
    const p = game.players[idx];

    if (idx === game.humanIdx) {
      // 玩家手牌（明牌，可点击）
      const drawnTile = p.hand.length === 14 ? p.hand[p.hand.length - 1] : null;
      p.hand.forEach((t, i) => {
        const isDrawn = drawnTile && i === p.hand.length - 1 && game.phase === 'discard' && game.currentIdx === idx;
        const el = this.createTileEl(t, { clickable: true, drawn: isDrawn });
        el.classList.add('tile-enter');
        if (t.id === this.selectedTileId) el.classList.add('selected');
        container.appendChild(el);
      });
    } else {
      // AI手牌（背面）
      const horizontal = (pos === 'left' || pos === 'right');
      for (let i = 0; i < p.hand.length; i++) {
        container.appendChild(this.createTileBack(horizontal));
      }
    }
  }

  // ---------- 弃牌 ----------
  renderDiscards(game, idx) {
    const pos = PLAYER_MAP[idx];
    const container = document.getElementById('discards-' + pos);
    container.innerHTML = '';
    const p = game.players[idx];
    p.discards.forEach((t, i) => {
      const isLast = game.lastDiscard && t.id === game.lastDiscard.id;
      const el = this.createTileEl(t, { small: true, lastDiscard: isLast });
      container.appendChild(el);
    });
  }

  // ---------- 副露(碰杠吃) ----------
  renderMelds(game, idx) {
    const pos = PLAYER_MAP[idx];
    const container = document.getElementById('melds-' + pos);
    container.innerHTML = '';
    const p = game.players[idx];
    p.melds.forEach(meld => {
      const group = document.createElement('div');
      group.className = 'meld-group';
      meld.tiles.forEach((t, i) => {
        if (meld.type === 'angang') {
          // 暗杠: 两端扣着，中间明
          group.appendChild(i === 0 || i === 3 ? this.createTileBack(false) : this.createTileEl(t, { small: true }));
        } else {
          group.appendChild(this.createTileEl(t, { small: true }));
        }
      });
      container.appendChild(group);
    });
  }

  // ---------- 信息栏 ----------
  renderInfo(game) {
    document.getElementById('tiles-count').textContent = game.tilesLeft;
    const seat = game.players[game.currentIdx].seat;
    document.getElementById('current-turn').textContent = SEAT_NAMES[seat] || seat;
  }

  // ---------- 操作面板 ----------
  showActions(actions, game) {
    const panel = document.getElementById('action-panel');
    panel.style.display = 'flex';
    // 清除旧的吃选项
    const oldChi = panel.querySelector('.chi-options');
    if (oldChi) oldChi.remove();

    const btnHu = panel.querySelector('.btn-hu');
    const btnGang = panel.querySelector('.btn-gang');
    const btnPeng = panel.querySelector('.btn-peng');
    const btnChi = panel.querySelector('.btn-chi');

    btnHu.style.display = actions.hu ? '' : 'none';
    btnGang.style.display = (actions.gang || actions.angang || actions.jiagang) ? '' : 'none';
    btnPeng.style.display = actions.peng ? '' : 'none';
    btnChi.style.display = actions.chi ? '' : 'none';

    if (actions.gang) btnGang.textContent = '杠';
    if (actions.angang) btnGang.textContent = '暗杠';
    if (actions.jiagang) btnGang.textContent = '加杠';
  }

  hideActions() {
    const panel = document.getElementById('action-panel');
    panel.style.display = 'none';
    const oldChi = panel.querySelector('.chi-options');
    if (oldChi) oldChi.remove();
  }

  showChiOptions(options, tile, callback) {
    const panel = document.getElementById('action-panel');
    let chiDiv = panel.querySelector('.chi-options');
    if (!chiDiv) {
      chiDiv = document.createElement('div');
      chiDiv.className = 'chi-options';
      panel.appendChild(chiDiv);
    }
    chiDiv.innerHTML = '';
    options.forEach(vals => {
      const opt = document.createElement('div');
      opt.className = 'chi-option';
      vals.forEach(v => {
        const t = { suit: tile.suit, value: v };
        const d = tileDisplay(t);
        const span = document.createElement('span');
        span.className = 'tile tile-small suit-' + tile.suit;
        span.innerHTML = `<span class="tile-num">${d.num}</span>`;
        opt.appendChild(span);
      });
      opt.addEventListener('click', () => callback(vals));
      chiDiv.appendChild(opt);
    });
  }

  // ---------- 结果 ----------
  showResult(game) {
    const modal = document.getElementById('result-modal');
    modal.style.display = 'flex';
    const title = document.getElementById('result-title');
    const detail = document.getElementById('result-detail');

    if (game.winner === null) {
      title.textContent = '流 局';
      detail.innerHTML = '牌墙摸完，无人胡牌';
    } else {
      const p = game.players[game.winner];
      const isHuman = game.winner === game.humanIdx;
      const typeText = game.winType === 'zimo' ? '自摸' : '胡牌';
      title.textContent = isHuman ? '🎉 你赢了！' : `${SEAT_NAMES[p.seat]}家 ${typeText}`;
      let html = `<div>${typeText}`;
      if (game.winTile) html += `：${tileName(game.winTile)}`;
      html += '</div>';
      // 显示胡牌者的手牌
      html += '<div style="margin-top:12px;display:flex;gap:2px;justify-content:center;flex-wrap:wrap;">';
      for (const t of p.hand) {
        const d = tileDisplay(t);
        html += `<span class="tile tile-small suit-${t.suit}"><span class="tile-num">${d.num}</span>${d.suitLabel ? '<span class="tile-suit">' + d.suitLabel + '</span>' : ''}</span>`;
      }
      html += '</div>';
      detail.innerHTML = html;
    }
  }

  hideResult() {
    document.getElementById('result-modal').style.display = 'none';
  }

  // ---------- 点击 ----------
  _onTileClick(tile) {
    if (this.selectedTileId === tile.id) {
      // 二次点击 = 打出
      this.selectedTileId = null;
      if (this.onDiscardCb) this.onDiscardCb(tile.id);
    } else {
      this.selectedTileId = tile.id;
      // 刷新高亮
      document.querySelectorAll('#hand-bottom .tile').forEach(el => {
        el.classList.toggle('selected', el.dataset.id === tile.id);
      });
    }
  }

  // ---------- 听牌提示 ----------
  showTingHint(hand) {
    const existing = document.getElementById('ting-hint');
    if (existing) existing.remove();
    if (hand.length !== 13) return;
    const tings = getTingTiles(hand);
    if (tings.length === 0) return;
    const div = document.createElement('div');
    div.id = 'ting-hint';
    div.style.cssText = 'position:fixed;bottom:120px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.7);padding:6px 14px;border-radius:8px;font-size:13px;color:#ffd700;z-index:15;display:flex;align-items:center;gap:6px;';
    div.innerHTML = '听牌：' + tings.map(t => tileName(t)).join(' ');
    document.body.appendChild(div);
  }

  clearTingHint() {
    const existing = document.getElementById('ting-hint');
    if (existing) existing.remove();
  }
}
