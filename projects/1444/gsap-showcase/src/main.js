/* GSAP Skills Showcase — main.js (clean rewrite) */

const log = (msg) => {
  const el = document.getElementById('diag');
  if (el) el.textContent = msg;
  console.log('[gsap-showcase]', msg);
};

window.addEventListener('error', (e) => {
  log('ERR: ' + (e.message || e.type));
  console.error(e);
});

document.addEventListener('DOMContentLoaded', () => {
  try {
    // ── plugin registration with graceful degrade ──
    const plugins = [];
    if (window.ScrollTrigger) plugins.push(ScrollTrigger);
    if (window.Flip) plugins.push(Flip);
    if (window.Draggable) plugins.push(Draggable);
    if (window.MotionPathPlugin) plugins.push(MotionPathPlugin);
    if (window.SplitText) plugins.push(SplitText);
    if (plugins.length) gsap.registerPlugin(...plugins);
    log('plugins: ' + plugins.length + ' loaded');

    safe('sidebar', initSidebarSpy);
    safe('hero',    initHero);
    safe('eases',   initEases);
    safe('stagger', initStagger);
    safe('timeline',initTimeline);
    safe('scrub',   initScrub);
    safe('parallax',initParallax);
    safe('flip',    initFlip);
    safe('drag',    initDraggable);
    safe('path',    initMotionPath);
    safe('split',   initSplitText);
    safe('utils',   initUtils);
    safe('perf',    initPerf);

    log('ready ✓');
  } catch (e) {
    log('boot fail: ' + e.message);
    console.error(e);
  }
});

function safe(name, fn) {
  try { fn(); } catch (e) {
    console.error('[' + name + ']', e);
    log(name + ' fail: ' + e.message);
  }
}

/* ── 侧栏导航 ── */
function initSidebarSpy() {
  const links = document.querySelectorAll('.nav-link');
  const map = {};
  links.forEach(l => { map[l.dataset.target] = l; });

  if (window.ScrollTrigger) {
    document.querySelectorAll('.section').forEach(sec => {
      ScrollTrigger.create({
        trigger: sec,
        start: 'top 40%',
        end: 'bottom 40%',
        onToggle: (self) => {
          if (self.isActive) {
            links.forEach(l => l.classList.remove('active'));
            map[sec.id]?.classList.add('active');
          }
        }
      });
    });
  }
  links.forEach(l => {
    l.addEventListener('click', e => {
      e.preventDefault();
      const t = document.getElementById(l.dataset.target);
      if (t) t.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

/* ── HERO ── */
function initHero() {
  // 文字进场 — 不依赖 SplitText
  gsap.from('#heroTitle', { y: 60, opacity: 0, duration: 1, ease: 'power3.out' });
  gsap.from('#heroSub',   { y: 20, opacity: 0, duration: 0.8, delay: 0.4, ease: 'power2.out' });
  gsap.from('.chip', {
    opacity: 0, y: 10, scale: 0.8, stagger: 0.05,
    duration: 0.5, delay: 0.8, ease: 'back.out(2)'
  });
  gsap.to('.scroll-hint', {
    y: 8, opacity: 0.4, repeat: -1, yoyo: true, duration: 1, ease: 'sine.inOut'
  });
}

/* ── ① EASES ── */
const EASES = [
  'none', 'power1.out', 'power2.out', 'power3.out', 'power4.out',
  'back.out(1.7)', 'elastic.out(1, 0.3)', 'bounce.out',
  'expo.out', 'circ.out', 'sine.inOut', 'power2.inOut'
];

function initEases() {
  const grid = document.getElementById('easeGrid');
  EASES.forEach(name => {
    const row = document.createElement('div');
    row.className = 'ease-row';
    row.innerHTML =
      '<div class="ease-label">' + name + '</div>' +
      '<div class="ease-track"><div class="ease-ball" data-ease="' + name + '"></div></div>';
    grid.appendChild(row);
  });

  const playAll = () => {
    document.querySelectorAll('.ease-ball').forEach(ball => {
      gsap.fromTo(ball, { x: 0 }, {
        x: () => ball.parentElement.offsetWidth - 36,
        duration: 1.6,
        ease: ball.dataset.ease,
        overwrite: true
      });
    });
  };
  document.getElementById('playEases').addEventListener('click', playAll);

  if (window.ScrollTrigger) {
    ScrollTrigger.create({
      trigger: '#core', start: 'top 70%', once: true,
      onEnter: playAll
    });
  } else {
    setTimeout(playAll, 500);
  }
}

/* ── ② STAGGER ── */
function initStagger() {
  const grid = document.getElementById('staggerGrid');
  for (let i = 0; i < 100; i++) {
    const c = document.createElement('div');
    c.className = 'cell';
    grid.appendChild(c);
  }
  const cells = grid.querySelectorAll('.cell');

  const run = (fromMode) => {
    gsap.fromTo(cells,
      { scale: 0, rotation: 0 },
      {
        scale: 1, rotation: 180,
        duration: 0.5, ease: 'back.out(1.5)',
        stagger: { amount: 0.8, from: fromMode, grid: [10, 10] }
      }
    );
  };

  document.querySelectorAll('[data-stagger]').forEach(b => {
    b.addEventListener('click', () => run(b.dataset.stagger));
  });

  if (window.ScrollTrigger) {
    ScrollTrigger.create({
      trigger: '#stagger', start: 'top 70%', once: true,
      onEnter: () => run('center')
    });
  } else {
    setTimeout(() => run('center'), 800);
  }
}

/* ── ③ TIMELINE ── */
let masterTL;
function initTimeline() {
  masterTL = gsap.timeline({
    paused: true,
    defaults: { duration: 0.6, ease: 'power2.out' },
    onUpdate: () => {
      const s = document.getElementById('tlProgress');
      if (s && !s.dragging) s.value = masterTL.progress();
    }
  });
  masterTL
    .to('#tlA', { x: 300 })
    .to('#tlB', { x: 300, rotation: 180 }, '<0.2')
    .to('#tlC', { x: 300, scale: 1.5 }, '<0.2')
    .to('#tlD', { x: 300, backgroundColor: '#f43f5e' }, '<0.2')
    .to('.tl-box', {
      x: 0, rotation: 0, scale: 1, backgroundColor: '#3b82f6',
      stagger: 0.1, duration: 0.4
    }, '>0.4');

  document.getElementById('tlPlay').addEventListener('click', () => masterTL.play());
  document.getElementById('tlPause').addEventListener('click', () => masterTL.pause());
  document.getElementById('tlReverse').addEventListener('click', () => masterTL.reverse());
  document.getElementById('tlRestart').addEventListener('click', () => masterTL.restart());

  const slider = document.getElementById('tlProgress');
  slider.addEventListener('mousedown', () => slider.dragging = true);
  slider.addEventListener('touchstart', () => slider.dragging = true);
  slider.addEventListener('mouseup', () => slider.dragging = false);
  slider.addEventListener('touchend', () => slider.dragging = false);
  slider.addEventListener('input', (e) => {
    masterTL.pause();
    masterTL.progress(parseFloat(e.target.value));
  });

  if (window.ScrollTrigger) {
    ScrollTrigger.create({
      trigger: '#timeline', start: 'top 60%', once: true,
      onEnter: () => masterTL.play()
    });
  } else {
    setTimeout(() => masterTL.play(), 1200);
  }
}

/* ── ④ SCRUB ── */
function initScrub() {
  if (!window.ScrollTrigger) return;
  const obj = { val: 0 };
  gsap.to('#scrubCircle', {
    strokeDashoffset: 0,
    scrollTrigger: { trigger: '#scrub', start: 'top top', end: 'bottom bottom', scrub: 0.5 }
  });
  gsap.to(obj, {
    val: 100,
    scrollTrigger: {
      trigger: '#scrub', start: 'top top', end: 'bottom bottom', scrub: 0.5,
      onUpdate: () => { document.getElementById('scrubNum').textContent = Math.round(obj.val); }
    }
  });
}

/* ── ⑤ PIN + PARALLAX ── */
function initParallax() {
  if (!window.ScrollTrigger) return;
  const tl = gsap.timeline({
    scrollTrigger: {
      trigger: '#pin', start: 'top top', end: '+=1500',
      scrub: 0.6, pin: true
    }
  });
  tl.to('.layer-back',  { yPercent: -30, ease: 'none' }, 0)
    .to('.layer-mid',   { yPercent: -100, ease: 'none' }, 0)
    .to('.layer-front', { yPercent: -300, scale: 1.5, ease: 'none' }, 0);
}

/* ── ⑥ FLIP ── */
function initFlip() {
  const board = document.getElementById('flipBoard');
  const apply = (mode) => {
    if (window.Flip) {
      const state = Flip.getState('.flip-card');
      board.classList.remove('grid-mode', 'list-mode', 'stack-mode');
      board.classList.add(mode + '-mode');
      Flip.from(state, { duration: 0.7, ease: 'power2.inOut', stagger: 0.04, absolute: true });
    } else {
      board.classList.remove('grid-mode', 'list-mode', 'stack-mode');
      board.classList.add(mode + '-mode');
    }
  };
  document.getElementById('flipGrid').addEventListener('click', () => apply('grid'));
  document.getElementById('flipList').addEventListener('click', () => apply('list'));
  document.getElementById('flipStack').addEventListener('click', () => apply('stack'));
}

/* ── ⑦ DRAGGABLE ── */
function initDraggable() {
  const cards = gsap.utils.toArray('.drag-card');
  const container = document.getElementById('dragContainer');
  const cw = container.offsetWidth;
  const ch = container.offsetHeight;
  cards.forEach((c) => {
    gsap.set(c, {
      x: gsap.utils.random(0, Math.max(0, cw - 90)),
      y: gsap.utils.random(0, Math.max(0, ch - 90)),
      rotation: gsap.utils.random(-15, 15)
    });
  });
  if (window.Draggable) {
    Draggable.create('.drag-card', {
      bounds: '#dragContainer',
      type: 'x,y',
      onPress: function () { gsap.to(this.target, { scale: 1.1, zIndex: 99, duration: 0.2 }); },
      onRelease: function () { gsap.to(this.target, { scale: 1, duration: 0.2 }); }
    });
  }
}

/* ── ⑧ MOTIONPATH ── */
function initMotionPath() {
  const play = () => {
    if (window.MotionPathPlugin) {
      gsap.fromTo('#rocket', {},
        {
          motionPath: {
            path: '#theLine',
            align: '#theLine',
            alignOrigin: [0.5, 0.5],
            autoRotate: true
          },
          duration: 2.5, ease: 'power2.inOut', overwrite: true
        }
      );
    }
  };
  document.getElementById('playPath').addEventListener('click', play);
  if (window.ScrollTrigger) {
    ScrollTrigger.create({
      trigger: '#motionpath', start: 'top 60%', once: true, onEnter: play
    });
  } else {
    setTimeout(play, 600);
  }
}

/* ── ⑨ SPLITTEXT ── */
let currentSplit;
function initSplitText() {
  const target = document.getElementById('splitTarget');
  const original = target.textContent;

  const fallback = (mode) => {
    // 没有 SplitText 时手动按空格 / 字符切
    target.textContent = '';
    let parts;
    if (mode === 'words') parts = original.split(/(\s+)/);
    else parts = original.split('');
    const nodes = parts.map(p => {
      const span = document.createElement('span');
      span.textContent = p;
      span.style.display = 'inline-block';
      target.appendChild(span);
      return span;
    });
    gsap.from(nodes, {
      y: 40, opacity: 0, rotationX: -90,
      stagger: mode === 'words' ? 0.08 : 0.025,
      duration: 0.7, ease: 'back.out(1.7)'
    });
  };

  const run = (mode) => {
    if (!window.SplitText) { fallback(mode); return; }
    try {
      if (currentSplit) currentSplit.revert();
      target.textContent = original;
      currentSplit = new SplitText('#splitTarget', { type: mode });
      const items = currentSplit[mode];
      gsap.from(items, {
        y: 40, opacity: 0, rotationX: -90,
        stagger: mode === 'chars' ? 0.025 : 0.08,
        duration: 0.7, ease: 'back.out(1.7)'
      });
    } catch (e) {
      console.error('split fail', e);
      fallback(mode);
    }
  };

  document.querySelectorAll('[data-split]').forEach(b => {
    b.addEventListener('click', () => run(b.dataset.split));
  });
  if (window.ScrollTrigger) {
    ScrollTrigger.create({
      trigger: '#splittext', start: 'top 60%', once: true,
      onEnter: () => run('chars')
    });
  } else {
    setTimeout(() => run('chars'), 800);
  }
}

/* ── ⑩ UTILS ── */
function initUtils() {
  const input = document.getElementById('utilsInput');
  const box = document.getElementById('utilsBox');

  const clampFn = gsap.utils.clamp(20, 80);
  const mapDeg  = gsap.utils.mapRange(0, 100, 0, 360);
  const mapX    = gsap.utils.mapRange(0, 100, 0, 400);
  const snapFn  = gsap.utils.snap(25);
  const normFn  = gsap.utils.normalize(0, 100);

  const update = () => {
    const v = parseFloat(input.value);
    document.getElementById('vIn').textContent = v;
    document.getElementById('vClamp').textContent = clampFn(v);
    document.getElementById('vMap').textContent = Math.round(mapDeg(v)) + '°';
    document.getElementById('vSnap').textContent = snapFn(v);
    document.getElementById('vNorm').textContent = normFn(v).toFixed(2);
    gsap.to(box, { x: mapX(v), rotation: mapDeg(v), duration: 0.3, ease: 'power2.out' });
  };
  input.addEventListener('input', update);
  update();
}

/* ── ⑪ PERFORMANCE ── */
function initPerf() {
  document.getElementById('perfRun').addEventListener('click', () => {
    const w = document.querySelector('.perf-track').offsetWidth - 40;
    gsap.fromTo('#perfBad',  { left: 10 }, { left: w, duration: 2, repeat: 1, yoyo: true, ease: 'power1.inOut', overwrite: true });
    gsap.fromTo('#perfGood', { x: 0 },     { x: w,    duration: 2, repeat: 1, yoyo: true, ease: 'power1.inOut', overwrite: true });
  });
}
