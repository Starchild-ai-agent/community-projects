const DAYS_CN = ['日','一','二','三','四','五','六'];
function pad(n){ return String(n).padStart(2,'0'); }

function dayLabel(days){
  if(!days||days.length===0) return '仅一次';
  if(days.length===7) return '每天';
  const wk=[1,2,3,4,5], wkend=[0,6];
  if(wk.every(d=>days.includes(d))&&days.length===5) return '工作日';
  if(wkend.every(d=>days.includes(d))&&days.length===2) return '周末';
  return days.sort((a,b)=>a-b).map(d=>'周'+DAYS_CN[d]).join('、');
}

let alarms = JSON.parse(localStorage.getItem('alarms_v1')||'[]');
let triggered = null;
let ringCtx = null;
let canCheck = false;

function save(){ localStorage.setItem('alarms_v1', JSON.stringify(alarms)); }

function render(){
  document.getElementById('count-badge').textContent = alarms.length+' 个';
  const list = document.getElementById('alarm-list');
  if(alarms.length===0){
    list.innerHTML='<li style="display:block"><div class="empty-tip">暂无闹钟，点击上方添加 ☝️</div></li>';
    return;
  }
  list.innerHTML = alarms.map(a=>`
    <li id="li-${a.id}" class="${triggered===a.id?'triggered':''}">
      <label class="alarm-toggle">
        <input type="checkbox" ${a.on?'checked':''} onchange="toggle('${a.id}',this.checked)">
        <span class="toggle-slider"></span>
      </label>
      <div class="alarm-time-big" style="color:${a.on?'#fff':'var(--sub)'}">${a.time}</div>
      <div class="alarm-info">
        <div class="alarm-label">${a.label||'闹钟'}</div>
        <div class="alarm-repeat">${dayLabel(a.days)}</div>
      </div>
      <span class="alarm-sound-icon">${a.on?'🔔':'🔕'}</span>
      <button class="btn-delete" onclick="deleteAlarm('${a.id}')" title="删除">✕</button>
    </li>
  `).join('');
}

function addAlarm(){
  const time = document.getElementById('input-time').value;
  if(!time){ alert('请选择时间'); return; }
  const label = document.getElementById('input-label').value.trim();
  const days = [...document.querySelectorAll('.day-btn.active')].map(b=>+b.dataset.day);
  alarms.push({ id: Date.now().toString(36), time, label, days, on: true });
  alarms.sort((a,b)=>a.time.localeCompare(b.time));
  save(); render();
  document.getElementById('input-label').value='';
  document.querySelectorAll('.day-btn.active').forEach(b=>b.classList.remove('active'));
}

document.querySelectorAll('.day-btn').forEach(btn=>{
  btn.addEventListener('click',()=>btn.classList.toggle('active'));
});

function toggle(id,on){
  const a=alarms.find(x=>x.id===id);
  if(a){ a.on=on; save(); render(); }
}

function deleteAlarm(id){
  alarms=alarms.filter(x=>x.id!==id);
  save(); render();
}

function updateClock(){
  const now=new Date();
  const h=pad(now.getHours()), m=pad(now.getMinutes()), s=pad(now.getSeconds());
  document.getElementById('current-time').textContent=`${h}:${m}`;
  document.getElementById('current-seconds').textContent=`:${s}`;
  const wkdays=['星期日','星期一','星期二','星期三','星期四','星期五','星期六'];
  document.getElementById('current-date').textContent=
    `${now.getFullYear()} 年 ${now.getMonth()+1} 月 ${now.getDate()} 日　${wkdays[now.getDay()]}`;
  if(canCheck && now.getSeconds()===0) checkAlarms(now);
}

function checkAlarms(now){
  if(triggered) return;
  const hhmm=`${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const dow=now.getDay();
  for(const a of alarms){
    if(!a.on||a.time!==hhmm) continue;
    if(a.days.length>0&&!a.days.includes(dow)) continue;
    triggerAlarm(a); break;
  }
}

function triggerAlarm(alarm){
  triggered=alarm.id; render();
  document.getElementById('modal-time').textContent=alarm.time;
  document.getElementById('modal-label').textContent=alarm.label||'时间到了！';
  document.getElementById('modal-overlay').classList.add('show');
  startRing();
}

function startRing(){
  try{
    const ctx=new(window.AudioContext||window.webkitAudioContext)();
    ringCtx=ctx;
    let count=0;
    (function beep(){
      if(count>=16||!ringCtx) return;
      const osc=ctx.createOscillator(), gain=ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type='sine';
      osc.frequency.setValueAtTime(880,ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440,ctx.currentTime+0.3);
      gain.gain.setValueAtTime(0.45,ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001,ctx.currentTime+0.45);
      osc.start(ctx.currentTime); osc.stop(ctx.currentTime+0.45);
      count++; setTimeout(beep,650);
    })();
  }catch(e){}
}

function dismissAlarm(){
  if(ringCtx){ try{ringCtx.close();}catch(e){} ringCtx=null; }
  const alarm=alarms.find(x=>x.id===triggered);
  if(alarm&&alarm.days.length===0){ alarm.on=false; save(); }
  triggered=null;
  document.getElementById('modal-overlay').classList.remove('show');
  render();
}

setInterval(updateClock,1000);
updateClock();
render();
setTimeout(()=>{ canCheck=true; },3000);
