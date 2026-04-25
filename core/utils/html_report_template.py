"""Generates the full self-contained HTML string from pre-computed report data."""
import json


_PALETTE = ["#0DBBA8","#22D3EE","#10B981","#F59E0B","#F43F5E","#8B5CF6","#38BDF8","#a78bfa","#34D399","#FB923C","#E879F9","#4ADE80"]

_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,sans-serif;background:#050e0d;color:#eef5f3;min-height:100vh}
a{color:#0DBBA8}
.page{max-width:1400px;margin:0 auto;padding:32px 24px}
/* header */
.report-header{display:flex;align-items:center;justify-content:space-between;padding:28px 32px;background:linear-gradient(135deg,#0c1e1c,#091a18);border:1px solid #1a3330;border-radius:16px;margin-bottom:32px}
.rh-left h1{font-size:1.7rem;font-weight:800;background:linear-gradient(90deg,#0DBBA8,#22D3EE);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.rh-left p{color:#7ea89f;font-size:0.8rem;margin-top:4px}
.rh-actions{display:flex;align-items:center;gap:12px}
.rh-badge{background:rgba(13,187,168,.15);border:1px solid rgba(13,187,168,.3);border-radius:20px;padding:6px 16px;font-size:0.75rem;color:#0DBBA8;font-weight:700}
/* kpi */
.kpi-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:16px;margin-bottom:32px}
@media(max-width:1100px){.kpi-grid{grid-template-columns:repeat(3,1fr)}}
.kpi{background:#0c1e1c;border:1px solid #1a3330;border-radius:14px;padding:20px 18px;position:relative;overflow:hidden}
.kpi::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse at top left,rgba(13,187,168,.07),transparent 70%)}
.kpi-label{font-size:.67rem;text-transform:uppercase;letter-spacing:.08em;color:#3D6860;font-weight:700;margin-bottom:8px}
.kpi-value{font-size:1.6rem;font-weight:800;color:#eef5f3;font-variant-numeric:tabular-nums}
.kpi-sub{font-size:.7rem;color:#7ea89f;margin-top:4px}
/* section */
.section{margin-bottom:32px}
.section-title{font-size:.8rem;text-transform:uppercase;letter-spacing:.1em;color:#3D6860;font-weight:700;margin-bottom:16px;display:flex;align-items:center;gap:8px}
.section-title::after{content:'';flex:1;height:1px;background:#1a3330}
/* card */
.card{background:#0c1e1c;border:1px solid #1a3330;border-radius:14px;padding:24px}
.chart-wrap{position:relative}
/* grid layouts */
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.grid-3{display:grid;grid-template-columns:2fr 1fr;gap:20px}
@media(max-width:900px){.grid-2,.grid-3{grid-template-columns:1fr}}
/* table */
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{color:#3D6860;text-transform:uppercase;font-size:.65rem;letter-spacing:.07em;padding:8px 12px;border-bottom:1px solid #1a3330;text-align:left}
td{padding:10px 12px;border-bottom:1px solid #112220;color:#b0cac7}
tr:hover td{background:rgba(13,187,168,.04)}
td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;color:#eef5f3}
td.teal{color:#0DBBA8;font-weight:700}
/* badge */
.badge{display:inline-block;border-radius:20px;padding:2px 10px;font-size:.7rem;font-weight:700}
.badge-btc{background:rgba(251,191,36,.12);color:#FBBF24}
.badge-usdt{background:rgba(16,185,129,.12);color:#10B981}
.badge-other{background:rgba(139,92,246,.12);color:#8B5CF6}
/* footer */
.report-footer{text-align:center;color:#3D6860;font-size:.72rem;margin-top:48px;padding-top:24px;border-top:1px solid #1a3330}
/* mobile overrides */
@media(max-width:768px){
  .kpi-grid{grid-template-columns:1fr 1fr}
  .report-header{flex-direction:column;align-items:flex-start;gap:16px;padding:20px}
  .rh-actions{width:100%;display:flex;justify-content:space-between;align-items:center}
  .page{padding:16px 12px}
  .card{padding:16px}
}
.btn-download{background:#0DBBA8;color:#050e0d;border:none;border-radius:20px;padding:8px 16px;font-size:.75rem;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:6px;transition:opacity .2s}
.btn-download:hover{opacity:.8}
"""


_JS_STATIC = """
const P = window.RDATA;
const COLORS = ["#0DBBA8","#22D3EE","#10B981","#F59E0B","#F43F5E","#8B5CF6","#38BDF8","#a78bfa","#34D399","#FB923C"];
const DEF = {
  responsive:true, maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'rgba(5,14,13,.95)',borderColor:'rgba(13,187,168,.25)',borderWidth:1,titleColor:'#7ea89f',bodyColor:'#eef5f3'}},
  scales:{
    x:{grid:{display:false},ticks:{color:'#3D6860',font:{size:10}},border:{display:false}},
    y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#3D6860',font:{size:10},callback:v=>'$'+(v>=1000?(v/1000).toFixed(0)+'K':v)},border:{display:false}}
  }
};
const DEF_COUNT = JSON.parse(JSON.stringify(DEF));
DEF_COUNT.scales.y.ticks.callback = v=>v;

function grad(ctx,c1,c2){const g=ctx.createLinearGradient(0,0,0,300);g.addColorStop(0,c1);g.addColorStop(1,c2);return g;}

// 1. Daily volume (line)
(()=>{
  const ctx=document.getElementById('c-daily').getContext('2d');
  const g=grad(ctx,'rgba(13,187,168,.45)','rgba(13,187,168,.02)');
  new Chart(ctx,{type:'line',data:{labels:P.daily_labels,datasets:[
    {label:'MXN Volume',data:P.daily_vols,borderColor:'#0DBBA8',backgroundColor:g,fill:true,tension:.4,pointRadius:0,pointHoverRadius:5},
    {label:'7d MA',data:P.ma7,borderColor:'#22D3EE',backgroundColor:'transparent',borderDash:[4,4],tension:.4,pointRadius:0,borderWidth:1.5}
  ]},options:{...DEF,plugins:{...DEF.plugins,legend:{display:true,labels:{color:'#7ea89f',font:{size:11},usePointStyle:true,pointStyleWidth:8}}}}});
})();

// 2. Monthly volume (bar)
(()=>{
  const ctx=document.getElementById('c-monthly').getContext('2d');
  const g=grad(ctx,'rgba(34,211,238,.5)','rgba(34,211,238,.05)');
  new Chart(ctx,{type:'bar',data:{labels:P.monthly_labels,datasets:[
    {label:'Volume',data:P.monthly_vols,backgroundColor:g,borderColor:'#22D3EE',borderWidth:1.5,borderRadius:6}
  ]},options:DEF});
})();

// 3. Account comparison
(()=>{
  const ctx=document.getElementById('c-accounts').getContext('2d');
  new Chart(ctx,{type:'bar',data:{labels:P.acc_labels,datasets:[
    {label:'MXN Volume',data:P.acc_vols,backgroundColor:COLORS,borderRadius:8,borderSkipped:false}
  ]},options:{...DEF,scales:{...DEF.scales,x:{...DEF.scales.x,ticks:{color:'#7ea89f',font:{size:11}}}}}});
})();

// 4. Top buyers horizontal bar
(()=>{
  const ctx=document.getElementById('c-buyers').getContext('2d');
  new Chart(ctx,{type:'bar',data:{labels:P.tb_labels,datasets:[
    {label:'Volume',data:P.tb_vols,backgroundColor:'rgba(13,187,168,.7)',borderRadius:4,borderSkipped:false}
  ]},options:{...DEF,indexAxis:'y',plugins:{...DEF.plugins,legend:{display:false}},scales:{
    x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#3D6860',font:{size:10},callback:v=>'$'+(v>=1000?(v/1000).toFixed(0)+'K':v)},border:{display:false}},
    y:{grid:{display:false},ticks:{color:'#b0cac7',font:{size:10}},border:{display:false}}
  }}});
})();

// 5. Payment method donut
(()=>{
  const ctx=document.getElementById('c-methods').getContext('2d');
  new Chart(ctx,{type:'doughnut',data:{labels:P.pm_labels,datasets:[
    {data:P.pm_vols,backgroundColor:COLORS,borderColor:'#0c1e1c',borderWidth:3,hoverOffset:6}
  ]},options:{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{
    legend:{display:true,position:'right',labels:{color:'#7ea89f',font:{size:10},padding:14,usePointStyle:true}},
    tooltip:{backgroundColor:'rgba(5,14,13,.95)',borderColor:'rgba(13,187,168,.25)',borderWidth:1,titleColor:'#7ea89f',bodyColor:'#eef5f3',callbacks:{label:ctx=>' $'+(ctx.raw/1000).toFixed(0)+'K'}}
  }}});
})();

// 6. Crypto split donut
(()=>{
  const ctx=document.getElementById('c-crypto').getContext('2d');
  new Chart(ctx,{type:'doughnut',data:{labels:P.crypto_labels,datasets:[
    {data:P.crypto_vols,backgroundColor:['#FBBF24','#10B981','#8B5CF6'],borderColor:'#0c1e1c',borderWidth:3,hoverOffset:6}
  ]},options:{responsive:true,maintainAspectRatio:false,cutout:'62%',plugins:{
    legend:{display:true,position:'right',labels:{color:'#7ea89f',font:{size:10},padding:14,usePointStyle:true}},
    tooltip:{backgroundColor:'rgba(5,14,13,.95)',borderColor:'rgba(13,187,168,.25)',borderWidth:1,titleColor:'#7ea89f',bodyColor:'#eef5f3',callbacks:{label:ctx=>' $'+(ctx.raw/1000).toFixed(0)+'K'}}
  }}});
})();

// 7. Hour of day
(()=>{
  const ctx=document.getElementById('c-hours').getContext('2d');
  const maxV=Math.max(...P.hour_counts);
  new Chart(ctx,{type:'bar',data:{labels:P.hour_labels,datasets:[
    {label:'Trades',data:P.hour_counts,backgroundColor:P.hour_counts.map(v=>`rgba(13,187,168,${0.15+0.75*(v/maxV)})`),borderRadius:4,borderSkipped:false}
  ]},options:{...DEF_COUNT,scales:{x:{grid:{display:false},ticks:{color:'#3D6860',font:{size:9}},border:{display:false}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#3D6860',font:{size:10},callback:v=>v},border:{display:false}}}}});
})();

// 8. Day of week
(()=>{
  const ctx=document.getElementById('c-dow').getContext('2d');
  new Chart(ctx,{type:'bar',data:{labels:P.dow_names,datasets:[
    {label:'Volume',data:P.dow_vols,backgroundColor:'rgba(34,211,238,.55)',borderColor:'#22D3EE',borderWidth:1.5,borderRadius:6,borderSkipped:false},
    {label:'Trades',data:P.dow_counts,backgroundColor:'rgba(16,185,129,.4)',borderColor:'#10B981',borderWidth:1.5,borderRadius:6,borderSkipped:false,yAxisID:'y2'}
  ]},options:{...DEF,plugins:{...DEF.plugins,legend:{display:true,labels:{color:'#7ea89f',font:{size:11},usePointStyle:true}}},scales:{
    x:{grid:{display:false},ticks:{color:'#7ea89f',font:{size:11,weight:'600'}},border:{display:false}},
    y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#3D6860',font:{size:10},callback:v=>'$'+(v>=1000?(v/1000).toFixed(0)+'K':v)},border:{display:false}},
    y2:{position:'right',grid:{display:false},ticks:{color:'#3D6860',font:{size:10}},border:{display:false}}
  }}});
})();

// 9. Trade size histogram
(()=>{
  const ctx=document.getElementById('c-hist').getContext('2d');
  new Chart(ctx,{type:'bar',data:{labels:P.bucket_labels,datasets:[
    {label:'# Trades',data:P.bucket_counts,backgroundColor:COLORS,borderRadius:6,borderSkipped:false}
  ]},options:{...DEF_COUNT,scales:{
    x:{grid:{display:false},ticks:{color:'#7ea89f',font:{size:10}},border:{display:false}},
    y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#3D6860',font:{size:10},callback:v=>v},border:{display:false}}
  }}});
})();

// Download Offline HTML
function downloadHtml(){
  const html = document.documentElement.outerHTML;
  const blob = new Blob([html], {type: 'text/html'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const safeDate = P.meta.generated.replace(/[^a-zA-Z0-9]/g, '_');
  a.download = `WillGang_Report_${safeDate}.html`;
  a.click();
}
"""


def generate_report_html(data: dict) -> str:
    m = data["meta"]
    j = json.dumps(data)

    def _kpi(label, value, sub=""):
        return f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-sub">{sub}</div></div>'

    def _crypto_badge(c):
        cls = "badge-btc" if c.upper()=="BTC" else ("badge-usdt" if c.upper()=="USDT" else "badge-other")
        return f'<span class="badge {cls}">{c.upper()}</span>'

    # Recent trades table rows
    rows_html = ""
    for r in data.get("recent_rows", []):
        cb = _crypto_badge(r["crypto"])
        rows_html += f"""<tr>
          <td>{r['date']}</td>
          <td class="teal">{r['buyer']}</td>
          <td>{r['method']}</td>
          <td class="num">{r['amount']}</td>
          <td>{cb}</td>
          <td style="color:#7ea89f;font-size:.78rem">{r['account']}</td>
        </tr>"""

    # Buyer table rows
    buyer_rows = ""
    for i, (lbl, vol, cnt, avg) in enumerate(zip(
        data["tb_labels"], data["tb_vols"], data["tb_cnts"], data["tb_avgs"]
    )):
        buyer_rows += f"""<tr>
          <td style="color:#7ea89f;font-size:.78rem">#{i+1}</td>
          <td class="teal">{lbl}</td>
          <td class="num">${vol:,.0f}</td>
          <td class="num">{cnt}</td>
          <td class="num">${avg:,.0f}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WillGang Trading Report — {m.get('period','')}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>{_CSS}</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="report-header">
    <div class="rh-left">
      <h1>⚡ WillGang Trading Report</h1>
      <p>Period: {m.get('period','N/A')} &nbsp;·&nbsp; Generated {m['generated']}</p>
    </div>
    <div class="rh-actions">
      <div class="rh-badge">Noones · All Accounts</div>
      <button class="btn-download" onclick="downloadHtml()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        Save Offline
      </button>
    </div>
  </div>

  <!-- KPI STRIP -->
  <div class="kpi-grid">
    {_kpi("Total Trades", f"{m['total_trades']:,}", "last 90 days")}
    {_kpi("Total MXN Volume", m['total_vol_fmt'], "last 90 days")}
    {_kpi("Avg Trade Size", m['avg_size_fmt'], "MXN per trade")}
    {_kpi("Largest Trade", m['max_trade_fmt'], "single transaction")}
    {_kpi("Unique Buyers", f"{m['uniq_buyers']:,}", "distinct buyers")}
    {_kpi("Active Accounts", f"{m.get('active_accounts', 0)}", "receiving trades")}
  </div>

  <!-- DAILY TREND -->
  <div class="section">
    <div class="section-title">📈 Daily Volume — Last 90 Days</div>
    <div class="card">
      <div class="chart-wrap" style="height:220px"><canvas id="c-daily"></canvas></div>
    </div>
  </div>

  <!-- MONTHLY + ACCOUNTS -->
  <div class="section grid-2">
    <div>
      <div class="section-title">📅 Monthly MXN Volume</div>
      <div class="card">
        <div class="chart-wrap" style="height:200px"><canvas id="c-monthly"></canvas></div>
      </div>
    </div>
    <div>
      <div class="section-title">🏦 Account Comparison</div>
      <div class="card">
        <div class="chart-wrap" style="height:200px"><canvas id="c-accounts"></canvas></div>
      </div>
    </div>
  </div>

  <!-- TOP BUYERS -->
  <div class="section">
    <div class="section-title">🏆 Top Buyers by Volume</div>
    <div class="grid-3" style="align-items:start">
      <div class="card">
        <div class="chart-wrap" style="height:320px"><canvas id="c-buyers"></canvas></div>
      </div>
      <div class="card" style="padding:0;overflow:auto">
        <table>
          <thead><tr><th>#</th><th>Buyer</th><th style="text-align:right">Volume</th><th style="text-align:right">Trades</th><th style="text-align:right">Avg</th></tr></thead>
          <tbody>{buyer_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- PAYMENT METHODS + CRYPTO SPLIT -->
  <div class="section grid-2">
    <div>
      <div class="section-title">💳 Payment Method Distribution</div>
      <div class="card">
        <div class="chart-wrap" style="height:220px"><canvas id="c-methods"></canvas></div>
      </div>
    </div>
    <div>
      <div class="section-title">🔗 Crypto Split (by MXN equivalent)</div>
      <div class="card">
        <div class="chart-wrap" style="height:220px"><canvas id="c-crypto"></canvas></div>
      </div>
    </div>
  </div>

  <!-- HOUR + DOW -->
  <div class="section grid-2">
    <div>
      <div class="section-title">🕐 Trades by Hour of Day</div>
      <div class="card">
        <div class="chart-wrap" style="height:180px"><canvas id="c-hours"></canvas></div>
      </div>
    </div>
    <div>
      <div class="section-title">📆 Day of Week Activity</div>
      <div class="card">
        <div class="chart-wrap" style="height:180px"><canvas id="c-dow"></canvas></div>
      </div>
    </div>
  </div>

  <!-- TRADE SIZE HISTOGRAM -->
  <div class="section">
    <div class="section-title">📊 Trade Size Distribution</div>
    <div class="card">
      <div class="chart-wrap" style="height:160px"><canvas id="c-hist"></canvas></div>
    </div>
  </div>

  <!-- RECENT TRADES TABLE -->
  <div class="section">
    <div class="section-title">🕒 25 Most Recent Completed Trades</div>
    <div class="card" style="padding:0;overflow:auto">
      <table>
        <thead><tr><th>Date</th><th>Buyer</th><th>Method</th><th style="text-align:right">Amount</th><th>Crypto</th><th>Account</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="report-footer">WillGang Command Center &nbsp;·&nbsp; Generated {m['generated']} &nbsp;·&nbsp; Data source: Noones Platform</div>
</div>

<script>window.RDATA = {j};</script>
<script>{_JS_STATIC}</script>
</body>
</html>"""
