(function(){
  const slides = Array.from(document.querySelectorAll('.slide'));
  const total = slides.length;
  let cur = 0;
  const pg = document.getElementById('pg');
  const progress = document.getElementById('progress');
  const stage = document.getElementById('stage');

  /* ---- fit 1280x720 stage to viewport ---- */
  function fit(){
    const s = Math.min(window.innerWidth/1280, window.innerHeight/720);
    stage.style.transform = `scale(${s})`;
  }
  window.addEventListener('resize', fit); fit();

  /* ---- starfield ---- */
  const cv = document.getElementById('stars'), cx = cv.getContext('2d');
  let W,H,pts=[];
  function initStars(){
    W = cv.width = window.innerWidth; H = cv.height = window.innerHeight;
    const n = Math.min(70, Math.floor(W*H/22000));
    pts = Array.from({length:n},()=>({
      x:Math.random()*W, y:Math.random()*H,
      vx:(Math.random()-.5)*.25, vy:(Math.random()-.5)*.25,
      r:Math.random()*1.6+.4
    }));
  }
  window.addEventListener('resize', initStars); initStars();
  function drawStars(){
    cx.clearRect(0,0,W,H);
    for(const p of pts){
      p.x+=p.vx; p.y+=p.vy;
      if(p.x<0||p.x>W) p.vx*=-1;
      if(p.y<0||p.y>H) p.vy*=-1;
      cx.beginPath(); cx.arc(p.x,p.y,p.r,0,7);
      cx.fillStyle='rgba(255,140,70,.35)'; cx.fill();
    }
    for(let i=0;i<pts.length;i++) for(let j=i+1;j<pts.length;j++){
      const a=pts[i],b=pts[j],dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;
      if(d2<16900){
        cx.beginPath(); cx.moveTo(a.x,a.y); cx.lineTo(b.x,b.y);
        cx.strokeStyle=`rgba(255,107,26,${.12*(1-d2/16900)})`; cx.lineWidth=1; cx.stroke();
      }
    }
    requestAnimationFrame(drawStars);
  }
  drawStars();

  /* ---- cursor glow + card tilt ---- */
  const glow = document.getElementById('cursor-glow');
  document.addEventListener('mousemove', e=>{
    glow.style.left = e.clientX+'px'; glow.style.top = e.clientY+'px';
  });
  document.querySelectorAll('.card,.three .w,.media').forEach(el=>{
    el.addEventListener('mousemove', e=>{
      const r = el.getBoundingClientRect();
      const rx = ((e.clientY-r.top)/r.height-.5)*-7;
      const ry = ((e.clientX-r.left)/r.width-.5)*9;
      el.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-3px)`;
    });
    el.addEventListener('mouseleave', ()=>{ el.style.transform=''; });
  });


  /* ---- counters ---- */
  function runCounters(slide){
    slide.querySelectorAll('[data-count]').forEach(el=>{
      const raw=el.dataset.count, target=parseFloat(raw), dec=(raw.split('.')[1]||'').length, dur=1400, t0=performance.now();
      function tick(now){
        const p=Math.min((now-t0)/dur,1), e=1-Math.pow(1-p,3), v=target*e;
        el.textContent = dec ? v.toFixed(dec) : Math.round(v).toLocaleString();
        if(p<1) requestAnimationFrame(tick);
      }
      el.textContent='0'; requestAnimationFrame(tick);
    });
  }

  /* ---- navigation ---- */
  function show(i){
    if(i<0||i>=total||i===cur && slides[i].classList.contains('active')) {}
    i=Math.max(0,Math.min(total-1,i));
    slides[cur].classList.remove('active');
    cur=i;
    slides[cur].classList.add('active');
    pg.textContent=`${cur+1} / ${total}`;
    progress.style.width=((cur+1)/total*100)+'%';
    runCounters(slides[cur]);
  }
  const next=()=>{ if(cur<total-1) show(cur+1); };
  const prev=()=>{ if(cur>0) show(cur-1); };
  document.getElementById('next').onclick=next;
  document.getElementById('prev').onclick=prev;
  document.addEventListener('keydown',e=>{
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();next();}
    if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();prev();}
    if(e.key==='Home')show(0);
    if(e.key==='End')show(total-1);
  });
  document.getElementById('deck').addEventListener('click',e=>{
    if(e.target.closest('.nav')||e.target.closest('.langbtn'))return;
    (e.clientX>window.innerWidth/2)?next():prev();
  });

  /* ---- language toggle ---- */
  const bEN=document.getElementById('bEN'), bCN=document.getElementById('bCN');
  function setLang(l){
    document.body.classList.toggle('lang-en',l==='en');
    document.body.classList.toggle('lang-cn',l==='cn');
    bEN.classList.toggle('on',l==='en');
    bCN.classList.toggle('on',l==='cn');
  }
  bEN.onclick=e=>{e.stopPropagation();setLang('en');};
  bCN.onclick=e=>{e.stopPropagation();setLang('cn');};

  // ---- projects marquee: duplicate for seamless loop ----
  const pjt = document.getElementById('pjtrack');
  if(pjt){ pjt.innerHTML += pjt.innerHTML; }

  show(0);
})();

/* ===== Interactive Goals demo (real-UI style: messages pop in) ===== */
(function(){
  const body = document.getElementById('gbody');
  if(!body) return;
  const slide = document.getElementById('goalsSlide');
  const tabs = Array.from(document.querySelectorAll('.gtab'));

  const TBL = `<table class="tbl"><thead><tr><th>Wallet</th><th>30D PnL</th><th>ROI</th></tr></thead><tbody><tr class="hl"><td class="mono">0x8def…edae</td><td class="gain">+$10.0M</td><td>+18.5%</td></tr><tr><td class="mono">0xab11…4d5f</td><td class="gain">+$6.9M</td><td>+108%</td></tr><tr><td class="mono">0x66f4…8836</td><td class="gain">+$4.9M</td><td>+72.5%</td></tr></tbody></table>`;

  const WC = `<div class="gwc26"><div class="gstrip">${'<span></span>'.repeat(10)}</div><div class="gwh"><div class="lg">FIFA WC 26</div><div class="lv"><i></i>Starchild AI</div></div><div class="gtabs2"><span class="on">Overview</span><span>Matches</span><span>Mispricings</span><span>Groups</span><span>Odds</span><span>Method</span></div><div class="ghero"><div class="glb">PREDICTIONS DASHBOARD</div><div class="gti">FIFA World Cup <em class="g">20</em><em class="r">26</em></div><div class="gsu">Dixon-Coles Poisson + Elo model vs live Kalshi markets</div></div><div class="gteams"><div class="gt f"><div class="fl">\u{1F1E6}\u{1F1F7}</div><div class="cd">ARG</div><div class="pc">8.7%</div></div><div class="gt"><div class="fl">\u{1F1EB}\u{1F1F7}</div><div class="cd">FRA</div><div class="pc">8.5%</div></div><div class="gt"><div class="fl">\u{1F1EA}\u{1F1F8}</div><div class="cd">ESP</div><div class="pc">7.6%</div></div><div class="gt"><div class="fl">\u{1F1E7}\u{1F1F7}</div><div class="cd">BRA</div><div class="pc">7.0%</div></div></div><div class="gcols"><div class="gcard"><div class="ct">Model vs Market</div><div class="grow"><span>FRA</span><div class="gtr"><div class="gfl g" style="width:47%"></div></div><strong>8.5%</strong></div><div class="grow"><span>ESP</span><div class="gtr"><div class="gfl g" style="width:42%"></div></div><strong>7.6%</strong></div><div class="grow"><span>ARG</span><div class="gtr"><div class="gfl b" style="width:48%"></div></div><strong>8.7%</strong></div><div class="grow"><span>BRA</span><div class="gtr"><div class="gfl b" style="width:39%"></div></div><strong>7.0%</strong></div></div><div class="gcard"><div class="ct">Mispricing Alerts</div><div class="gal"><span class="fl">\u{1F1EB}\u{1F1F7}</span><span class="nm">FRA France<em>Market higher</em></span><span class="ed down">-9.6%</span></div><div class="gal"><span class="fl">\u{1F1EA}\u{1F1F8}</span><span class="nm">ESP Spain<em>Market higher</em></span><span class="ed down">-8.6%</span></div><div class="gal"><span class="fl">\u{1F1EE}\u{1F1F9}</span><span class="nm">ITA Italy<em>Underpriced</em></span><span class="ed up">+3.5%</span></div></div></div></div>`;

  const PREVIEW_EN = `<p>Here's the generated dashboard preview.</p><p class="glink"><a href="https://community.iamstarchild.com/1365-wc2026-predictions/" target="_blank" rel="noopener">https://community.iamstarchild.com/1365-wc2026-predictions/</a></p>${WC}`;
  const PREVIEW_CN = `<p>\u751f\u6210\u597d\u4e86\uff0c\u8fd9\u662f\u770b\u677f\u9884\u89c8\u3002</p><p class="glink"><a href="https://community.iamstarchild.com/1365-wc2026-predictions/" target="_blank" rel="noopener">https://community.iamstarchild.com/1365-wc2026-predictions/</a></p>${WC}`;

  const SCRIPTS = {
    build: [
      {r:'u', en:'Build me a World Cup predictions dashboard — my model vs Kalshi market prices.', cn:'帮我做一个世界杯预测看板，对比我的模型和 Kalshi 市场价格。'},
      {r:'a', en:'Done. Dark theme, 6 tabs: Overview · Predictions · Mispricings · Groups · Odds · Methodology. Mispriced markets get flagged automatically.', cn:'做好了。深色主题，六个页签：总览、比赛预测、错价提醒、小组赛、夺冠赔率、方法论。被市场定错价的盘口，系统会自动标出来。'},
      {r:'u', en:'Can you show the finished dashboard?', cn:'做好的看板能给我看看吗？'},
      {r:'a', wide:true, embed:true, en: PREVIEW_EN, cn: PREVIEW_CN}
    ],
    trade: [
      {r:'u', en:'Find me a profitable trader on Hyperliquid who trades both crypto and stocks.', cn:'在 Hyperliquid 上帮我找一个加密和美股都做的盈利交易员。'},
      {r:'a', wide:true, en:`Pulled the 30-day leaderboard. Wallet #1 is the only one trading crypto, stocks, commodities & indices:${TBL}`, cn:`查完 30 天榜单了。1 号钱包是唯一一个加密、美股、商品、指数全都做的：${TBL}`},
      {r:'u', en:'Copy-trade him with my wallet. Go.', cn:'用我的钱包跟他单，开始吧。'},
      {r:'a', en:'<b>✓ Live.</b> Copy-trade engine deployed — syncing positions every 5 min · 8% stop · 25% take-profit.', cn:'<b>✓ 已上线。</b>跟单引擎部署完成——每 5 分钟同步一次持仓，止损 8%，止盈 25%。'}
    ],
    grow: [
      {r:'u', en:"I'm a creator on X & YouTube. Every morning at 8am, send me trending topics in my niche.", cn:'我在 X 和 YouTube 做内容。每天早上 8 点，把我赛道里的热门话题发给我。'},
      {r:'a', wide:true, en:'<b>Good morning — 3 high-potential topics:</b><br>1. xAI: Voice Cloning via API <span class="gain">· 203M views</span><br>2. Anthropic: NL Autoencoders <span class="gain">· 2.4M views</span><br>3. DeepMind: AI pointer demos <span class="gain">· 1.6M views</span><br>Reply 1, 2 or 3.', cn:'<b>早上好，今天有 3 个高潜力话题：</b><br>1. xAI：语音克隆 API 上线 <span class="gain">· 2.03 亿浏览</span><br>2. Anthropic：自然语言自编码器研究 <span class="gain">· 240 万浏览</span><br>3. DeepMind：AI 指针交互演示 <span class="gain">· 160 万浏览</span><br>回复 1、2 或 3 即可。'},
      {r:'u', en:'1 seems easiest.', cn:'就选 1 吧。'},
      {r:'a', en:'<b>✓ Drafts ready:</b> X long-form · thread · YouTube intro. Schedule them now?', cn:'<b>✓ 草稿写好了：</b>X 长文、推文串、YouTube 开场白。要现在就排期发布吗？'}
    ]
  };
  const ORDER = ['build','trade','grow'];
  let token = 0, current = 'build';

  const sleep = (ms, t) => new Promise(res => setTimeout(()=>res(t===token), ms));
  const lang = () => document.body.classList.contains('lang-cn') ? 'cn' : 'en';

  async function play(key){
    const t = ++token;
    current = key;
    tabs.forEach(b => b.classList.toggle('on', b.dataset.g === key));
    body.innerHTML = '';
    const msgs = SCRIPTS[key];
    for(const m of msgs){
      if(m.r === 'u'){
        if(!await sleep(500, t)) return;
        const el = document.createElement('div');
        el.className = 'gmsg u';
        el.innerHTML = m[lang()];
        body.appendChild(el);
        if(!await sleep(800, t)) return;
      } else {
        const ty = document.createElement('div');
        ty.className = 'gtyping';
        ty.innerHTML = '<span></span><span></span><span></span>';
        body.appendChild(ty);
        if(!await sleep(m.embed ? 700 : 1100, t)) return;
        ty.remove();
        const el = document.createElement('div');
        el.className = 'gmsg a' + (m.wide ? ' wide' : '');
        el.innerHTML = m[lang()];
        body.appendChild(el);
        if(!await sleep(m.embed ? 2200 : 1200, t)) return;
      }
    }
    if(!await sleep(6000, t)) return;
    if(slide.classList.contains('active')){
      play(ORDER[(ORDER.indexOf(key)+1) % ORDER.length]);
    }
  }

  tabs.forEach(b => b.addEventListener('click', e => { e.stopPropagation(); play(b.dataset.g); }));

  new MutationObserver(()=>{
    if(slide.classList.contains('active')) play(current);
    else token++;
  }).observe(slide, {attributes:true, attributeFilter:['class']});

  document.getElementById('bEN').addEventListener('click', ()=>{ if(slide.classList.contains('active')) play(current); });
  document.getElementById('bCN').addEventListener('click', ()=>{ if(slide.classList.contains('active')) play(current); });
})();
