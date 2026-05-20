#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEC 13F Dashboard (single-quarter MVP).

Reads the pre-computed summary.json (next to this file) and renders a single
HTML page with KPI cards + two ECharts bar charts + two tables.

To rebuild summary.json from a fresh SEC 13F dataset, run:
    python build_summary.py
"""

import json
import os
from pathlib import Path
from flask import Flask, jsonify, Response

BASE = Path(__file__).resolve().parent
SUMMARY = BASE / 'summary.json'

app = Flask(__name__)


@app.route('/api/summary')
def api_summary():
    data = {
        'dataset': {'quarters': [], 'filings_count': 0, 'holdings_count': 0},
        'top_managers_latest': [],
        'popular_holdings_latest': []
    }
    ready = False
    if SUMMARY.exists():
        try:
            data = json.loads(SUMMARY.read_text(encoding='utf-8'))
            ready = True
        except Exception:
            ready = False

    ds = data.get('dataset', {})
    quarters = ds.get('quarters', [])
    return jsonify({
        'counts': {
            'quarters': quarters,
            'filings': ds.get('filings_count', 0),
            'holdings': ds.get('holdings_count', 0)
        },
        'latest': quarters[0] if quarters else None,
        'top_managers': data.get('top_managers_latest', []),
        'popular': data.get('popular_holdings_latest', []),
        'summary_ready': ready,
    })


@app.route('/')
def home():
    html = """<!doctype html>
<html>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>13F Dashboard (Single Quarter)</title>
<script src='https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js'></script>
<style>
body{font-family:system-ui;background:#0b1020;color:#e5e7eb;margin:0}
.wrap{max-width:1200px;margin:20px auto;padding:0 14px}
.row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:12px}
.val{font-size:22px;font-weight:700}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
#c1,#c2{height:380px;background:#111827;border:1px solid #1f2937;border-radius:10px}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:7px;border-bottom:1px solid #1f2937;text-align:left}
button{background:#2563eb;color:#fff;border:none;border-radius:8px;padding:6px 10px;cursor:pointer}
</style>
</head>
<body>
<div class='wrap'>
  <div style='display:flex;justify-content:space-between;align-items:center'>
    <h2>SEC 13F Dashboard (Single-Quarter MVP)</h2>
    <button onclick='loadData()'>Refresh</button>
  </div>
  <div class='row'>
    <div class='card'><div>Quarters</div><div id='kq' class='val'>-</div></div>
    <div class='card'><div>Filings</div><div id='kf' class='val'>-</div></div>
    <div class='card'><div>Holdings Rows</div><div id='kh' class='val'>-</div></div>
    <div class='card'><div>Latest Quarter</div><div id='kl' class='val'>-</div></div>
  </div>
  <div class='grid2'>
    <div id='c1'></div><div id='c2'></div>
  </div>
  <div class='grid2'>
    <div class='card'><h3>Top Managers</h3><table id='t1'><thead><tr><th>Manager</th><th>CIK</th><th>$M</th></tr></thead><tbody></tbody></table></div>
    <div class='card'><h3>Popular Holdings</h3><table id='t2'><thead><tr><th>Issuer</th><th>CUSIP</th><th>Funds</th><th>$M</th></tr></thead><tbody></tbody></table></div>
  </div>
</div>
<script>
let c1 = null;
let c2 = null;
if (window.echarts) {
  c1 = echarts.init(document.getElementById('c1'));
  c2 = echarts.init(document.getElementById('c2'));
}
const fmt = n => Number(n||0).toLocaleString();
function fill(id, rows, cols){
  document.querySelector(id+' tbody').innerHTML = rows.map(r=>'<tr>'+cols.map(c=>'<td>'+(r[c]??'')+'</td>').join('')+'</tr>').join('');
}
async function loadData(){
  const r = await fetch('api/summary');
  const d = await r.json();
  document.getElementById('kq').textContent = (d.counts.quarters||[]).length;
  document.getElementById('kf').textContent = fmt(d.counts.filings);
  document.getElementById('kh').textContent = fmt(d.counts.holdings);
  document.getElementById('kl').textContent = d.latest||'-';
  const tm = d.top_managers||[];
  const ph = d.popular||[];

  fill('#t1', tm.slice(0,20), ['manager_name','cik','total_musd']);
  fill('#t2', ph.slice(0,20), ['issuer','cusip','fund_count','total_musd']);

  if (c1 && c2) {
    c1.setOption({backgroundColor:'#111827',title:{text:'Top Managers by Value ($M)',left:8,textStyle:{color:'#e5e7eb',fontSize:13}},grid:{left:150,right:15,top:45,bottom:20},xAxis:{type:'value',axisLabel:{color:'#9ca3af'}},yAxis:{type:'category',data:tm.slice(0,10).map(x=>x.manager_name),axisLabel:{color:'#9ca3af'}},series:[{type:'bar',data:tm.slice(0,10).map(x=>x.total_musd),itemStyle:{color:'#60a5fa'}}]});
    c2.setOption({backgroundColor:'#111827',title:{text:'Most Widely Held (fund count)',left:8,textStyle:{color:'#e5e7eb',fontSize:13}},grid:{left:130,right:15,top:45,bottom:20},xAxis:{type:'value',axisLabel:{color:'#9ca3af'}},yAxis:{type:'category',data:ph.slice(0,10).map(x=>x.issuer),axisLabel:{color:'#9ca3af'}},series:[{type:'bar',data:ph.slice(0,10).map(x=>x.fund_count),itemStyle:{color:'#34d399'}}]});
  }
}
window.addEventListener('resize',()=>{ if(c1&&c2){c1.resize();c2.resize();} });
loadData();
</script>
</body>
</html>"""
    return Response(html, mimetype='text/html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8787'))
    app.run(host='0.0.0.0', port=port)
