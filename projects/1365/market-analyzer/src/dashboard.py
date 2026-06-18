"""
Real-time web dashboard for the market analyzer.
Clean Fallout Pip-Boy terminal aesthetic.
"""

import asyncio
import json
import time

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute
from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket


class Dashboard:
    def __init__(self):
        self._clients: list[WebSocket] = []
        self._signal_history: list[dict] = []
        self._outcome_history: list[dict] = []
        self._tune_history: list[dict] = []
        self._latest_state: dict = {}

    def seed(self, outcomes: list[dict] = None, adjustments: list[dict] = None):
        """Preload panel histories (e.g. from disk) so a fresh page isn't empty."""
        if outcomes:
            self._outcome_history = list(outcomes)[-20:]
        if adjustments:
            self._tune_history = list(adjustments)[-15:]

    async def broadcast(self, event_type: str, data: dict):
        msg = json.dumps({"type": event_type, "data": data, "ts": time.time()})
        dead = []
        for ws in self._clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.remove(ws)

    async def push_signal(self, symbol: str, timeframe: str, analysis: dict):
        entry = {"symbol": symbol, "timeframe": timeframe, "ts": time.time(), **analysis}
        self._signal_history.append(entry)
        self._signal_history = self._signal_history[-100:]
        await self.broadcast("signal", entry)

    async def push_tier1(self, symbol: str, timeframe: str, score: float, regime: str):
        await self.broadcast("tier1", {
            "symbol": symbol, "timeframe": timeframe, "score": score, "regime": regime,
        })

    async def push_outcome(self, result: dict):
        self._outcome_history.append(result)
        self._outcome_history = self._outcome_history[-20:]
        await self.broadcast("outcome", result)

    async def push_state(self, state: dict):
        self._latest_state = state
        await self.broadcast("state", state)

    async def push_self_tune(self, adjustments: list):
        self._tune_history.extend(adjustments)
        self._tune_history = self._tune_history[-15:]
        await self.broadcast("self_tune", {"adjustments": adjustments})

    async def ws_endpoint(self, websocket: WebSocket):
        await websocket.accept()
        self._clients.append(websocket)
        try:
            await websocket.send_text(json.dumps({
                "type": "init",
                "data": {
                    "signals": self._signal_history[-20:],
                    "outcomes": self._outcome_history[-20:],
                    "adjustments": self._tune_history[-15:],
                    "state": self._latest_state,
                },
                "ts": time.time(),
            }))
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            if websocket in self._clients:
                self._clients.remove(websocket)

    async def index(self, request):
        return HTMLResponse(HTML)

    def get_app(self):
        return Starlette(routes=[
            Route("/", self.index),
            WebSocketRoute("/ws", self.ws_endpoint),
        ])


HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>STARCHILD TERMINAL</title>
<link href="https://fonts.googleapis.com/css2?family=VT323&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--g:#33ff00;--gd:#196600;--bg:#090b07;--r:#ff3030;--a:#ffaa00}

html,body{
  height:100%;overflow:hidden;
  font-family:'VT323',monospace;
  background:var(--bg);color:var(--g);
  font-size:18px;line-height:1.5;
}

/* subtle scanlines */
body::after{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:9999;
  background:repeating-linear-gradient(0deg,transparent 0px,transparent 2px,rgba(0,0,0,0.08) 2px,rgba(0,0,0,0.08) 4px);
}

/* vignette */
body::before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:9998;
  background:radial-gradient(ellipse at center,transparent 55%,rgba(0,0,0,0.55));
}

.app{display:flex;flex-direction:column;height:100vh}

/* ===== BANNER ===== */
.banner{
  text-align:center;
  padding:20px 20px 14px;
  border-bottom:2px solid var(--gd);
  background:linear-gradient(180deg,rgba(51,255,0,0.04) 0%,transparent 100%);
  flex-shrink:0;
}
.ascii{
  white-space:pre;
  font-size:15px;
  line-height:1.1;
  text-shadow:0 0 15px var(--g),0 0 40px rgba(51,255,0,0.15);
  letter-spacing:1px;
}
.tagline{
  margin-top:8px;
  font-size:16px;
  letter-spacing:8px;
  color:var(--gd);
}

/* ===== STATUS BAR ===== */
.bar{
  display:flex;justify-content:space-between;
  padding:6px 24px;
  border-bottom:1px solid var(--gd);
  font-size:16px;color:var(--gd);
  flex-shrink:0;
}
.bar .on{color:var(--g);text-shadow:0 0 8px var(--g)}
.bar .off{color:var(--r);text-shadow:0 0 8px var(--r)}

/* ===== MAIN GRID ===== */
.grid{
  display:flex;flex:1;overflow:hidden;
}

/* --- LEFT PANEL --- */
.left{
  width:280px;flex-shrink:0;
  border-right:1px solid var(--gd);
  padding:16px 20px;
  overflow-y:auto;
}
.hdr{
  font-size:15px;color:var(--gd);letter-spacing:3px;
  padding-bottom:6px;margin-bottom:10px;margin-top:18px;
  border-bottom:1px solid var(--gd);
}
.hdr:first-child{margin-top:0}
.row{
  display:flex;justify-content:space-between;
  padding:4px 0;
}
.row .k{color:var(--gd)}
.row .v{text-shadow:0 0 8px rgba(51,255,0,0.35)}
.pos{color:var(--g)!important}
.neg{color:var(--r)!important;text-shadow:0 0 8px rgba(255,48,48,0.35)!important}

.p-entry{
  padding:5px 0;
  border-bottom:1px dotted rgba(51,255,0,0.1);
}

/* --- CENTER LOG --- */
.mid{
  flex:1;display:flex;flex-direction:column;overflow:hidden;
}
.mid-hdr{
  padding:10px 20px;
  border-bottom:1px solid var(--gd);
  font-size:15px;color:var(--gd);letter-spacing:3px;
  flex-shrink:0;
}
.feed{
  flex:1;overflow-y:auto;
  padding:8px 0;
}

/* Log lines */
.ln{
  padding:6px 20px;
  border-bottom:1px solid rgba(51,255,0,0.03);
}
.ln .t{color:var(--gd);font-size:15px;margin-right:8px}

.ln.t1{color:var(--gd);padding:4px 20px}
.ln.px{color:var(--gd);padding:3px 20px;font-size:16px}
.ln.sig{
  background:rgba(51,255,0,0.025);
  border-left:3px solid var(--g);
  padding-left:17px;
  margin:4px 0;
}
.ln.sig.sl{border-left-color:var(--r);background:rgba(255,48,48,0.025)}
.ln.oc{border-left:3px solid var(--a);padding-left:17px;margin:4px 0}
.ln.tu{color:var(--a)}
.ln.sy{color:var(--gd)}

.buy{color:var(--g);text-shadow:0 0 10px var(--g);font-weight:bold;letter-spacing:1px}
.sell{color:var(--r);text-shadow:0 0 10px var(--r);font-weight:bold;letter-spacing:1px}

.rg{
  font-size:15px;padding:0 5px;
  border:1px solid var(--gd);
  margin-left:4px;
}
.rg.trending_up{border-color:var(--g);color:var(--g)}
.rg.trending_down{border-color:var(--r);color:var(--r)}
.rg.range{border-color:var(--a);color:var(--a)}
.rg.high_vol{border-color:#e050e0;color:#e050e0}
.rg.low_vol{border-color:#40e0e0;color:#40e0e0}

.cb{display:flex;height:4px;margin:5px 0;background:rgba(51,255,0,0.06);gap:1px}
.cb .bu{background:var(--g);box-shadow:0 0 4px var(--g)}
.cb .be{background:var(--r);box-shadow:0 0 4px var(--r)}

.sub{color:var(--gd);font-size:16px;margin-top:3px}

/* --- RIGHT PANEL --- */
.right{
  width:300px;flex-shrink:0;
  border-left:1px solid var(--gd);
  padding:16px 20px;
  overflow-y:auto;
}
.o-row{
  padding:6px 0;
  border-bottom:1px dotted rgba(51,255,0,0.08);
}
.ok{color:var(--g);text-shadow:0 0 8px var(--g);font-weight:bold}
.no{color:var(--r);text-shadow:0 0 8px var(--r);font-weight:bold}
.t-row{
  padding:5px 0;color:var(--a);
  border-bottom:1px dotted rgba(255,170,0,0.1);
}

::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--gd);border-radius:2px}
</style>
</head>
<body>
<div class="app">

<!-- BANNER -->
<div class="banner">
<pre class="ascii">
 ____  _____  _    ____   ____ _   _ ___ _     ____
/ ___||_   _|/ \\  |  _ \\ / ___| | | |_ _| |   |  _ \\
\\___ \\  | | / _ \\ | |_) | |   | |_| || || |   | | | |
 ___) | | |/ ___ \\|  _ &lt;| |___|  _  || || |___| |_| |
|____/  |_/_/   \\_\\_| \\_\\\\____|_| |_|___|_____|____/
</pre>
<div class="tagline">MARKET ANALYSIS TERMINAL</div>
</div>

<!-- STATUS BAR -->
<div class="bar">
  <span>STATUS: <span id="st" class="off">CONNECTING</span></span>
  <span>FEED: <span id="ws" class="off">---</span></span>
  <span id="ck">00:00:00</span>
</div>

<div class="grid">

  <!-- LEFT -->
  <div class="left">
    <div class="hdr">PORTFOLIO</div>
    <div class="row"><span class="k">EQUITY</span><span class="v" id="eq">$10,000</span></div>
    <div class="row"><span class="k">P/L</span><span class="v" id="pl">$0.00</span></div>
    <div class="row"><span class="k">DRAWDOWN</span><span class="v" id="dd">0.0%</span></div>
    <div class="row"><span class="k">EXPOSURE</span><span class="v" id="ex">$0</span></div>

    <div class="hdr">TRACK RECORD</div>
    <div class="row"><span class="k">WIN RATE</span><span class="v" id="wr">--%</span></div>
    <div class="row"><span class="k">SIGNALS</span><span class="v" id="ts2">0</span></div>
    <div class="row"><span class="k">AVG 1H</span><span class="v" id="a1">--</span></div>
    <div class="row"><span class="k">AVG 4H</span><span class="v" id="a4">--</span></div>

    <div class="hdr">POSITIONS</div>
    <div id="pp"><span class="sub">NONE</span></div>
  </div>

  <!-- CENTER -->
  <div class="mid">
    <div class="mid-hdr">LIVE FEED</div>
    <div class="feed" id="fd">
      <div class="ln sy"><span class="t">&gt;</span>STARCHILD TERMINAL v2.0 ONLINE</div>
      <div class="ln sy"><span class="t">&gt;</span>RECURSIVE SELF-IMPROVEMENT: ACTIVE</div>
      <div class="ln sy"><span class="t">&gt;</span>AWAITING MARKET DATA...</div>
    </div>
  </div>

  <!-- RIGHT -->
  <div class="right">
    <div class="hdr">OUTCOMES</div>
    <div id="oa"></div>

    <div class="hdr">SELF-TUNE</div>
    <div id="ta"></div>
  </div>

</div>
</div>

<script>
const $=id=>document.getElementById(id);
let ws;
setInterval(()=>{$('ck').textContent=new Date().toLocaleTimeString()},1000);

function connect(){
  const p=location.protocol==='https:'?'wss':'ws';
  ws=new WebSocket(p+'://'+location.host+'/ws');
  ws.onopen=()=>{
    $('st').textContent='ONLINE';$('st').className='on';
    $('ws').textContent='ACTIVE';$('ws').className='on';
    L('sy','LINK ESTABLISHED');
  };
  ws.onclose=()=>{
    $('st').textContent='OFFLINE';$('st').className='off';
    $('ws').textContent='DOWN';$('ws').className='off';
    L('sy','LINK LOST - RECONNECTING...');
    setTimeout(connect,3000);
  };
  ws.onmessage=e=>H(JSON.parse(e.data));
}

function H(m){
  if(m.type==='init'){
    (m.data.signals||[]).forEach(SIG);
    (m.data.outcomes||[]).forEach(o=>OUT(o,true));
    if((m.data.adjustments||[]).length)TU(m.data.adjustments,true);
    if(m.data.state)ST(m.data.state);
  }
  if(m.type==='signal')SIG(m.data);
  if(m.type==='tier1')T1(m.data);
  if(m.type==='tier1_info')PX(m.data);
  if(m.type==='outcome')OUT(m.data);
  if(m.type==='state')ST(m.data);
  if(m.type==='self_tune')TU(m.data.adjustments);
}

function now(){return new Date().toLocaleTimeString()}

function L(c,h){
  const f=$('fd'),d=document.createElement('div');
  d.className='ln '+c;
  d.innerHTML='<span class="t">'+now()+'</span> '+h;
  f.appendChild(d);f.scrollTop=f.scrollHeight;
  while(f.children.length>300)f.firstChild.remove();
}

function T1(d){
  L('t1',
    '<span class="pos">[ESCALATE]</span> '+d.symbol+' '+d.timeframe+
    ' score=<span class="pos">'+d.score.toFixed(2)+'</span>'+
    ' <span class="rg '+d.regime+'">'+d.regime.toUpperCase()+'</span>'+
    ' &rarr; SENDING TO LLM'
  );
}

function PX(d){
  const p=d.price||0;
  const c=d.change||0;
  const cs=c>=0?'<span class="pos">+'+c.toFixed(3)+'%</span>':'<span class="neg">'+c.toFixed(3)+'%</span>';
  const v=d.volume||0;
  const sc=d.score||0;
  const rg=d.regime||'?';
  const reasons=(d.reasons||[]).join(' ');
  const scColor=sc>=0.6?'pos':sc>=0.3?'':'';

  let line='[TICK] <b>'+d.symbol+'</b> $'+p.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})+
    ' '+cs+' vol:'+v.toLocaleString(undefined,{maximumFractionDigits:0})+
    ' <span class="rg '+rg+'">'+rg.toUpperCase()+'</span>';
  if(sc>0) line+=' score:<span class="'+(scColor)+'">'+sc.toFixed(2)+'</span>';
  if(reasons) line+=' <span style="color:var(--a)">['+reasons+']</span>';

  L('px',line);
}

function SIG(s){
  const bu=s.bull_conviction||0,be=s.bear_conviction||0,tot=bu+be||1;
  const rg=s.regime||'?';
  const lv=s.key_levels||{};
  const c=s.action==='SELL'?'sig sl':'sig';
  const ac=s.action==='BUY'?'buy':'sell';

  let h='<span class="'+ac+'">['+s.action+']</span> '+
    '<b>'+s.symbol+'</b> '+s.timeframe+
    '  STR:'+( s.signal_strength||0)+
    '  RISK:'+(s.risk||'?').toUpperCase()+
    '  <span class="rg '+rg+'">'+rg.toUpperCase()+'</span>'+
    '<div class="cb">'+
    '<div class="bu" style="width:'+(bu/tot*100).toFixed(0)+'%"></div>'+
    '<div class="be" style="width:'+(be/tot*100).toFixed(0)+'%"></div></div>'+
    '<div class="sub">'+
    'BULL:'+bu+' BEAR:'+be+
    '  S:'+(lv.support||'?')+' R:'+(lv.resistance||'?')+
    (s.suggested_size?'  SIZE:$'+Math.round(s.suggested_size):'')+
    '</div>';
  if(s.pattern)h+='<div class="sub"><span class="pos">PATTERN:</span> '+s.pattern+'</div>';
  if(s.reasoning)h+='<div class="sub">'+s.reasoning+'</div>';
  if(s.catalyst)h+='<div class="sub"><span style="color:var(--a)">CATALYST:</span> '+s.catalyst+'</div>';
  if(s.invalidation)h+='<div class="sub"><span class="neg">INVALIDATION:</span> '+s.invalidation+'</div>';

  L(c,h);
}

function fmtRet(r,k){
  const v=r[k];
  return (v===undefined||v===null)?'?':v;
}

function OUT(o,replay){
  const ok=o.correct,v=ok?'CORRECT':'WRONG',cl=ok?'ok':'no';
  const r=o.returns||{};
  const rks=Object.keys(r);
  const rstr=rks.length
    ? rks.map(k=>k+':'+fmtRet(r,k)+'%').join('  ')
    : '1h:?%  4h:?%';

  const a=$('oa'),d=document.createElement('div');
  d.className='o-row';
  d.innerHTML='<span class="'+cl+'">'+v+'</span> '+
    o.symbol+' '+o.action+' @'+(o.entry_price?.toFixed(2)||'?')+
    '<div class="sub">'+rstr+
    (o.hit_invalidation?' <span class="neg">[INVALIDATED]</span>':'')+'</div>';
  a.prepend(d);
  while(a.children.length>20)a.lastChild.remove();

  if(!replay){
    L('oc','[OUTCOME] <span class="'+cl+'">'+v+'</span> '+
      o.symbol+' '+o.action+' @'+(o.entry_price?.toFixed(2)||'?')+'  '+rstr);
  }
}

function TU(adj,replay){
  const a=$('ta');
  (adj||[]).forEach(x=>{
    const d=document.createElement('div');
    d.className='t-row';
    d.innerHTML=x.param+': '+x.old+' &rarr; '+x.new+
      '<div class="sub">'+( x.reason||'')+'</div>';
    a.prepend(d);
    if(!replay)L('tu','[TUNE] '+x.param+': '+x.old+' &rarr; '+x.new);
  });
  while(a.children.length>15)a.lastChild.remove();
}

function ST(s){
  if(s.portfolio){
    const p=s.portfolio;
    $('eq').textContent='$'+(p.equity||0).toLocaleString(undefined,{maximumFractionDigits:0});
    const pnl=p.realized_pnl||0;
    $('pl').textContent=(pnl>=0?'+':'')+' $'+pnl.toFixed(2);
    $('pl').className='v '+(pnl>=0?'pos':'neg');
    $('dd').textContent=(p.drawdown||0).toFixed(1)+'%';
    $('dd').className='v '+((p.drawdown||0)>10?'neg':'');
    const exp=Object.values(p.positions||{}).reduce((s,x)=>s+(x.size||0),0);
    $('ex').textContent='$'+exp.toLocaleString(undefined,{maximumFractionDigits:0});

    const pp=$('pp');
    const pos=Object.values(p.positions||{});
    if(!pos.length){pp.innerHTML='<span class="sub">NONE</span>'}
    else{pp.innerHTML=pos.map(x=>
      '<div class="p-entry">'+
      '<span style="color:'+(x.side==='long'?'var(--g)':'var(--r)')+';font-weight:bold">'+
      x.side.toUpperCase()+'</span> '+
      '<b>'+x.symbol+'</b> @'+x.entry_price?.toFixed(2)+
      ' $'+(x.size||0).toFixed(0)+
      ' <span class="'+((x.unrealized_pnl_pct||0)>=0?'pos':'neg')+'">'+(x.unrealized_pnl_pct||0).toFixed(2)+'%</span>'+
      '</div>'
    ).join('')}
  }
  if(s.outcomes){
    const o=s.outcomes;
    $('wr').textContent=(o.win_rate||0)+'%';
    $('wr').className='v '+((o.win_rate||0)>=50?'pos':'neg');
    $('ts2').textContent=o.total_signals||0;
    $('a1').textContent=(o.avg_return_1h||0)+'%';
    $('a1').className='v '+((o.avg_return_1h||0)>=0?'pos':'neg');
    $('a4').textContent=(o.avg_return_4h||0)+'%';
    $('a4').className='v '+((o.avg_return_4h||0)>=0?'pos':'neg');
  }
}

connect();
setInterval(()=>{if(ws&&ws.readyState===1)ws.send('ping')},30000);
</script>
</body>
</html>"""
