// ========== 主控制器 ==========
const DELAY = { ai: 600, action: 400, draw: 300 };

class GameController {
  constructor() {
    this.game = new MahjongGame();
    this.ui = new MahjongUI();
    this.busy = false;
  }

  init() {
    document.getElementById('btn-start').addEventListener('click', () => this.startGame());
    document.getElementById('btn-restart').addEventListener('click', () => this.restart());

    // 操作按钮
    document.querySelectorAll('.btn-action').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.action;
        this.handleHumanAction(action);
      });
    });

    // 出牌回调
    this.ui.onDiscardCb = (tileId) => this.handleHumanDiscard(tileId);
  }

  startGame() {
    document.getElementById('start-screen').style.display = 'none';
    document.getElementById('game-screen').style.display = 'block';
    this.game.reset();
    this.game.deal();
    this.ui.selectedTileId = null;
    this.ui.renderAll(this.game);
    this.ui.showTingHint(this.game.players[this.game.humanIdx].hand);
    // 东家(idx=0, AI)先摸牌
    this.nextTurn();
  }

  restart() {
    this.ui.hideResult();
    this.ui.clearTingHint();
    this.busy = false;
    this.game.reset();
    this.game.deal();
    this.ui.selectedTileId = null;
    this.ui.renderAll(this.game);
    this.ui.showTingHint(this.game.players[this.game.humanIdx].hand);
    this.nextTurn();
  }

  // ========== 回合控制 ==========
  async nextTurn() {
    if (this.game.gameOver) return;
    const idx = this.game.currentIdx;

    // 摸牌
    const drawn = this.game.draw(idx);
    if (!drawn) {
      // 流局
      this.ui.renderAll(this.game);
      this.ui.showResult(this.game);
      return;
    }
    this.ui.renderAll(this.game);

    // 检查自摸动作(胡/暗杠/加杠)
    const selfActions = this.game.checkSelfActions(idx);

    if (idx === this.game.humanIdx) {
      // 人类回合
      if (Object.keys(selfActions).length > 0) {
        this._pendingSelfActions = selfActions;
        this.ui.showActions(selfActions, this.game);
        this._waitingForSelfAction = true;
      }
      // 等待人类出牌...
    } else {
      // AI回合
      await this.sleep(DELAY.ai);
      await this.aiPlay(idx, selfActions);
    }
  }

  // ========== AI ==========
  async aiPlay(idx, selfActions) {
    if (this.game.gameOver) return;
    const p = this.game.players[idx];

    // 自摸后检查
    if (Object.keys(selfActions).length > 0) {
      const decision = MahjongAI.decideSelfAction(selfActions);
      if (decision === 'hu') {
        this.game.doHu(idx, null, true);
        this.ui.renderAll(this.game);
        this.ui.showResult(this.game);
        return;
      }
      if (typeof decision === 'object') {
        if (decision.type === 'angang') {
          this.game.doAnGang(idx, decision.key);
          this.ui.renderAll(this.game);
          await this.sleep(DELAY.action);
          // 杠后继续当前玩家的新摸牌回合
          await this.nextTurn();
          return;
        }
        if (decision.type === 'jiagang') {
          this.game.doJiaGang(idx, decision.key);
          this.ui.renderAll(this.game);
          await this.sleep(DELAY.action);
          await this.nextTurn();
          return;
        }
      }
    }

    // 出牌
    const tile = MahjongAI.chooseDiscard(p.hand, p.melds);
    this.game.discard(idx, tile.id);
    this.ui.renderAll(this.game);

    await this.sleep(DELAY.action);
    // 检查其他人能不能碰/杠/吃/胡
    await this.checkPostDiscard(tile, idx);
  }

  // ========== 出牌后检测 ==========
  async checkPostDiscard(tile, discardIdx) {
    if (this.game.gameOver) return;
    const actions = this.game.checkActions(tile, discardIdx);

    if (Object.keys(actions).length === 0) {
      // 无人响应，下一家
      this.game.nextPlayer();
      await this.sleep(DELAY.draw);
      this.nextTurn();
      return;
    }

    // 优先级: 胡 > 杠 > 碰 > 吃
    // 先检查AI的行动，人类的需要等操作
    const humanIdx = this.game.humanIdx;
    let humanActions = actions[humanIdx] || null;

    // 非人类玩家先决策
    let aiDecision = null;
    let aiIdx = -1;
    for (const [pIdx, acts] of Object.entries(actions)) {
      const pi = parseInt(pIdx);
      if (pi === humanIdx) continue;
      const decision = MahjongAI.decideAction(acts, this.game.players[pi].hand, this.game.players[pi].melds);
      if (decision !== 'pass') {
        // AI有更高优先级?
        if (!aiDecision || this.actionPriority(decision) > this.actionPriority(aiDecision)) {
          aiDecision = decision;
          aiIdx = pi;
        }
      }
    }

    // 人类有操作?
    if (humanActions) {
      // 如果AI要胡且人类不能胡，AI优先
      if (aiDecision === 'hu' && !humanActions.hu) {
        await this.executeAIAction(aiIdx, aiDecision, tile, actions[aiIdx]);
        return;
      }
      // 让人类选择
      this._pendingActions = actions;
      this._pendingDiscardTile = tile;
      this._pendingDiscardIdx = discardIdx;
      this._pendingAIDecision = aiDecision;
      this._pendingAIIdx = aiIdx;
      this.ui.showActions(humanActions, this.game);
      return;
    }

    // 只有AI
    if (aiDecision && aiDecision !== 'pass') {
      await this.executeAIAction(aiIdx, aiDecision, tile, actions[aiIdx]);
    } else {
      this.game.nextPlayer();
      await this.sleep(DELAY.draw);
      this.nextTurn();
    }
  }

  async executeAIAction(aiIdx, decision, tile, acts) {
    await this.sleep(DELAY.action);
    if (decision === 'hu') {
      this.game.doHu(aiIdx, tile, false);
      this.ui.renderAll(this.game);
      this.ui.showResult(this.game);
    } else if (decision === 'gang') {
      this.game.doGang(aiIdx, tile);
      this.ui.renderAll(this.game);
      await this.sleep(DELAY.action);
      this.nextTurn();
    } else if (decision === 'peng') {
      this.game.doPeng(aiIdx, tile);
      this.ui.renderAll(this.game);
      // 碰后AI需要出牌
      await this.sleep(DELAY.ai);
      const p = this.game.players[aiIdx];
      const discard = MahjongAI.chooseDiscard(p.hand, p.melds);
      this.game.discard(aiIdx, discard.id);
      this.ui.renderAll(this.game);
      await this.sleep(DELAY.action);
      await this.checkPostDiscard(discard, aiIdx);
    } else if (decision === 'chi') {
      const chiOption = acts.chi[0];
      this.game.doChi(aiIdx, tile, chiOption);
      this.ui.renderAll(this.game);
      await this.sleep(DELAY.ai);
      const p = this.game.players[aiIdx];
      const discard = MahjongAI.chooseDiscard(p.hand, p.melds);
      this.game.discard(aiIdx, discard.id);
      this.ui.renderAll(this.game);
      await this.sleep(DELAY.action);
      await this.checkPostDiscard(discard, aiIdx);
    }
  }

  // ========== 人类操作 ==========
  handleHumanDiscard(tileId) {
    if (this.game.gameOver) return;
    if (this.game.currentIdx !== this.game.humanIdx) return;
    if (this.game.phase !== 'discard') return;
    if (this._waitingForSelfAction) return; // 先响应自摸操作

    const tile = this.game.discard(this.game.humanIdx, tileId);
    if (!tile) return;
    this.ui.selectedTileId = null;
    this.ui.clearTingHint();
    this.ui.renderAll(this.game);

    // 检查其他人
    setTimeout(() => this.checkPostDiscard(tile, this.game.humanIdx), DELAY.action);
  }

  handleHumanAction(action) {
    if (this.game.gameOver) return;

    // 自摸后的操作(胡/暗杠/加杠)
    if (this._waitingForSelfAction) {
      const selfActions = this._pendingSelfActions;
      this._waitingForSelfAction = false;
      this._pendingSelfActions = null;
      this.ui.hideActions();

      if (action === 'hu' && selfActions.hu) {
        this.game.doHu(this.game.humanIdx, null, true);
        this.ui.renderAll(this.game);
        this.ui.showResult(this.game);
        return;
      }
      if (action === 'gang') {
        if (selfActions.angang && selfActions.angang.length > 0) {
          this.game.doAnGang(this.game.humanIdx, selfActions.angang[0]);
          this.ui.renderAll(this.game);
          setTimeout(() => this.nextTurn(), DELAY.action);
          return;
        }
        if (selfActions.jiagang && selfActions.jiagang.length > 0) {
          this.game.doJiaGang(this.game.humanIdx, selfActions.jiagang[0]);
          this.ui.renderAll(this.game);
          setTimeout(() => this.nextTurn(), DELAY.action);
          return;
        }
      }
      // pass - 继续等出牌
      this.ui.showTingHint(this.game.players[this.game.humanIdx].hand);
      return;
    }

    // 别人出牌后的操作
    const tile = this._pendingDiscardTile;
    const discardIdx = this._pendingDiscardIdx;
    const humanActions = this._pendingActions?.[this.game.humanIdx];
    if (!humanActions) return;

    this.ui.hideActions();
    this._pendingActions = null;

    if (action === 'pass') {
      // 检查AI是否有动作
      const aiD = this._pendingAIDecision;
      const aiI = this._pendingAIIdx;
      if (aiD && aiD !== 'pass') {
        this.executeAIAction(aiI, aiD, tile, this.game.checkActions(tile, discardIdx)[aiI]);
      } else {
        this.game.nextPlayer();
        setTimeout(() => this.nextTurn(), DELAY.draw);
      }
      return;
    }

    if (action === 'hu' && humanActions.hu) {
      this.game.doHu(this.game.humanIdx, tile, false);
      this.ui.renderAll(this.game);
      this.ui.showResult(this.game);
      return;
    }

    if (action === 'gang' && humanActions.gang) {
      this.game.doGang(this.game.humanIdx, tile);
      this.ui.renderAll(this.game);
      setTimeout(() => this.nextTurn(), DELAY.action);
      return;
    }

    if (action === 'peng' && humanActions.peng) {
      this.game.doPeng(this.game.humanIdx, tile);
      this.ui.renderAll(this.game);
      this.ui.showTingHint(this.game.players[this.game.humanIdx].hand);
      // 碰后等玩家出牌
      return;
    }

    if (action === 'chi' && humanActions.chi) {
      if (humanActions.chi.length === 1) {
        this.game.doChi(this.game.humanIdx, tile, humanActions.chi[0]);
        this.ui.renderAll(this.game);
        this.ui.showTingHint(this.game.players[this.game.humanIdx].hand);
      } else {
        // 多种吃法，让玩家选
        this.ui.showChiOptions(humanActions.chi, tile, (vals) => {
          this.ui.hideActions();
          this.game.doChi(this.game.humanIdx, tile, vals);
          this.ui.renderAll(this.game);
          this.ui.showTingHint(this.game.players[this.game.humanIdx].hand);
        });
      }
      return;
    }
  }

  actionPriority(a) {
    const p = { hu: 4, gang: 3, peng: 2, chi: 1 };
    return p[a] || 0;
  }

  sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
}

// ========== 启动 ==========
document.addEventListener('DOMContentLoaded', () => {
  const ctrl = new GameController();
  ctrl.init();
});
