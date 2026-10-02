"""Render index.html from data/page_data.json.

Run:  python scripts/build_page.py   (after scripts/compute_rates.py)
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "data" / "page_data.json").read_text())
OUT = ROOT / "index.html"

C, R, P = D["counts"], D["rates"], D["population"]
RACES = ["Black", "Hispanic", "White", "Asian"]
fmt = lambda n: f"{n:,}"
pct = lambda x: round(x * 100, 1)
share_simple = {r: pct(C["race_sex_simple"][r]["female_share"]) for r in RACES}
share_agg = {r: pct(C["race_sex_aggravated"][r]["female_share"]) for r in RACES}
black_div = sorted([(d["division"], d["Black_F"]["rate"], d["Black_M"]["rate"], d["Black_F"]["n"], d["Black_F"]["pop"])
                    for d in D["division_rates"] if d["Black_F"]["rate"] is not None], key=lambda z: -z[1])[:12]
by_div = {d[0]: d for d in black_div}
years = C["all_by_year"]
weapons = C["weapons"]
strong = weapons["STRONG-ARM (HANDS, FIST, FEET OR BODILY FORCE)"]
bw = R["Black"]
ratio = {r: (lambda v: int(v) if v == int(v) else v)(round(bw["F"] / R[r]["F"], 1)) for r in RACES[1:]}
divmap = [{"name": d["division"], "lat": C["centroids"][d["division"]]["lat"], "lon": C["centroids"][d["division"]]["lon"],
           "rows": [{"race": r, "F": d[f"{r}_F"]["n"], "M": d[f"{r}_M"]["n"], "rateF": d[f"{r}_F"]["rate"], "rateM": d[f"{r}_M"]["rate"]} for r in RACES]}
          for d in D["division_rates"]]

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Assault victims in Los Angeles</title>
  <meta name="description" content="Who gets assaulted in Los Angeles: 100,946 LAPD assault reports from 2020 to 2023, by race, sex and division, as rates per 100,000 residents." />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{ --bg: #0a0a0a; --surface: #121212; --border: #262626; --text: #f2f2f2; --muted: #8b8b8b; --blue: #2563eb; --blue-light: #93c5fd; --red: #ef4444; }}
    body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.6; }}
    a {{ color: var(--blue-light); text-decoration: none; }} a:hover {{ text-decoration: underline; }}
    header {{ border-bottom: 1px solid var(--border); padding: 28px 40px; display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap; }}
    header h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -0.3px; }}
    header p {{ color: var(--muted); margin-top: 4px; font-size: 13px; }}
    header nav {{ display: flex; gap: 20px; font-size: 13px; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 40px; }}
    .answer {{ background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--red); border-radius: 0 8px 8px 0; padding: 20px 24px; margin-bottom: 40px; max-width: 860px; }}
    .answer .q {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); margin-bottom: 8px; font-weight: 600; }}
    .answer p {{ font-size: 15px; line-height: 1.7; }}
    .answer p + p {{ margin-top: 8px; color: var(--muted); font-size: 14px; }}
    .section-title {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }}
    .note {{ font-size: 12px; color: var(--muted); margin: -6px 0 16px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 18px 20px; }}
    .card .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted); margin-bottom: 8px; }}
    .card .value {{ font-size: 26px; font-weight: 700; line-height: 1; }}
    .card .sub {{ font-size: 11px; color: var(--muted); margin-top: 5px; }}
    .red {{ color: var(--red); }} .blue {{ color: var(--blue-light); }}
    .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
    .section-end {{ margin-bottom: 40px; }}
    .chart-box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 22px 24px; }}
    .chart-box h3 {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
    .chart-sub {{ font-size: 11px; color: var(--muted); margin-bottom: 16px; line-height: 1.5; }}
    .chart-wrap {{ position: relative; height: 270px; }}
    .chart-wrap.tall {{ height: 360px; }}
    #map {{ height: 460px; border-radius: 6px; border: 1px solid var(--border); background: #111; }}
    .dark-tiles {{ filter: invert(100%) hue-rotate(180deg) grayscale(70%) brightness(85%) contrast(90%); }}
    .leaflet-popup-content-wrapper {{ background: #1a1a1a; color: var(--text); border-radius: 6px; border: 1px solid var(--border); }}
    .leaflet-popup-tip {{ background: #1a1a1a; }}
    .leaflet-popup-content {{ font-size: 12px; margin: 12px 14px; }}
    .leaflet-popup-content table {{ min-width: 0; font-size: 11px; margin-top: 6px; }}
    .leaflet-popup-content td, .leaflet-popup-content th {{ padding: 3px 6px; }}
    .table-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: auto; margin-bottom: 40px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 420px; }}
    thead tr {{ background: var(--bg); border-bottom: 1px solid var(--border); }}
    th {{ padding: 12px 16px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted); font-weight: 600; }}
    td {{ padding: 10px 16px; border-bottom: 1px solid var(--border); }}
    td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    tr:last-child td {{ border-bottom: none; }}
    .findings {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 40px; }}
    .finding {{ background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--blue); border-radius: 0 8px 8px 0; padding: 16px 20px; }}
    .finding.red {{ border-left-color: var(--red); }}
    .finding h4 {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; color: var(--text); }}
    .finding p {{ font-size: 12px; color: var(--muted); line-height: 1.5; }}
    footer {{ border-top: 1px solid var(--border); padding: 20px 40px; color: var(--muted); font-size: 12px; display: flex; gap: 20px; flex-wrap: wrap; }}
    @media (max-width: 768px) {{
      header, footer {{ padding: 20px; }} .container {{ padding: 20px; }}
      .charts, .findings {{ grid-template-columns: 1fr; }}
      .chart-box {{ padding: 18px 16px; }} #map {{ height: 360px; }}
    }}
  </style>
</head>
<body>

<header>
  <div>
    <h1>Assault victims in Los Angeles</h1>
    <p>LAPD reports, {D["window"]} · {fmt(C["total"])} assaults · Martin Ngoh</p>
  </div>
  <nav>
    <a href="https://github.com/mngoh/LA-Crime">Code &amp; notebooks</a>
    <a href="https://martinngoh.com">martinngoh.com</a>
  </nav>
</header>

<div class="container">

  <div class="answer">
    <div class="q">The question</div>
    <p>Black women are a far larger share of assault victims than women of any other group. Is that a higher rate of victimization, or just where assaults happen?</p>
    <p>A higher rate. Per 100,000 residents a year, Black women are assaulted {fmt(bw["F"])} times: {ratio["Hispanic"]} times the rate of Hispanic women, {ratio["White"]} times White women, {ratio["Asian"]} times Asian women, and more often than Hispanic or White men.</p>
  </div>

  <div class="section-title">Dataset</div>
  <div class="cards">
    <div class="card"><div class="label">Assaults</div><div class="value">{fmt(C["total"])}</div><div class="sub">reported Jan 2020 to Jun 2023</div></div>
    <div class="card"><div class="label">Simple assault</div><div class="value">{fmt(C["simple"])}</div><div class="sub">battery</div></div>
    <div class="card"><div class="label">Aggravated</div><div class="value">{fmt(C["aggravated"])}</div><div class="sub">with a deadly weapon</div></div>
    <div class="card"><div class="label">Known race and sex</div><div class="value blue">{fmt(C["known"])}</div><div class="sub">used for rates</div></div>
    <div class="card"><div class="label">Divisions</div><div class="value">{C["divisions"]}</div><div class="sub">LAPD areas</div></div>
    <div class="card"><div class="label">Median victim age</div><div class="value">{int(C["median_age"])}</div><div class="sub">middle half {int(C["age_iqr"][0])} to {int(C["age_iqr"][1])}</div></div>
  </div>

  <div class="charts">
    <div class="chart-box">
      <h3>Victimization rate by race and sex</h3>
      <div class="chart-sub">Assault victims per 100,000 residents per year, citywide. Population: ACS 2020 to 2024 five-year estimates.</div>
      <div class="chart-wrap"><canvas id="rateChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Female share of victims</h3>
      <div class="chart-sub">Black women outnumber Black men only in simple assault. In every category their share is the highest of any group.</div>
      <div class="chart-wrap"><canvas id="shareChart"></canvas></div>
    </div>
  </div>
  <div class="charts section-end">
    <div class="chart-box">
      <h3>Black women's rate by division</h3>
      <div class="chart-sub">Per 100,000 Black female residents per year, divisions with {fmt(D["min_pop"])} or more. Central includes Skid Row and many non-resident victims, which inflates its rate.</div>
      <div class="chart-wrap tall"><canvas id="divChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Victims by year</h3>
      <div class="chart-sub">Victims with known sex. 2023 covers January to June only.</div>
      <div class="chart-wrap tall"><canvas id="yearChart"></canvas></div>
    </div>
  </div>

  <div class="section-title">Findings</div>
  <div class="findings">
    <div class="finding red"><h4>The rate gap is real</h4><p>Black women's victimization rate is {fmt(bw["F"])} per 100,000 a year. Hispanic women: {fmt(R["Hispanic"]["F"])}. White women: {fmt(R["White"]["F"])}. Asian women: {fmt(R["Asian"]["F"])}. Population share does not explain it.</p></div>
    <div class="finding red"><h4>Closest to parity with men</h4><p>Black women are assaulted at {int(bw["ratio"]*100)}% of the rate of Black men. For Hispanic, White and Asian women the figure is {int(R["Hispanic"]["ratio"]*100)}%, {int(R["White"]["ratio"]*100)}% and {int(R["Asian"]["ratio"]*100)}%.</p></div>
    <div class="finding"><h4>Simple assault is where women outnumber men</h4><p>{share_simple["Black"]}% of Black simple-assault victims are women, the only group above 50%. In aggravated assault the share is {share_agg["Black"]}%, against {share_agg["Hispanic"]}% to {share_agg["Asian"]}% for other groups.</p></div>
    <div class="finding"><h4>South LA carries the counts, Central the rate</h4><p>77th Street ({fmt(by_div["77th Street"][3])}) and Southeast ({fmt(by_div["Southeast"][3])}) have the most Black female victims. Central has the highest rate ({fmt(black_div[0][1])}) on a small resident population.</p></div>
    <div class="finding"><h4>Mostly strong-arm</h4><p>{round(strong / C["total"] * 100)}% of all assaults involved hands, fists or feet rather than a weapon. Handguns appear in {fmt(weapons["HAND GUN"])}.</p></div>
    <div class="finding"><h4>What this does not show</h4><p>Why. These are reported assaults against residential population. The caveats below matter as much as the numbers.</p></div>
  </div>

  <div class="section-title">Map</div>
  <p class="note">Each marker is a division. Click one for counts and rates by race and sex.</p>
  <div id="map" class="section-end"></div>

  <div class="section-title">Caveats</div>
  <div class="findings">
    <div class="finding red"><h4>This shows what, not why</h4><p>The data says Black women are assaulted at a higher rate. It does not say why. Nothing here measures causes, offenders or circumstances.</p></div>
    <div class="finding red"><h4>Reported crimes only</h4><p>Every number is a report that reached LAPD. Willingness to report, and police recording practice, differ by group, by area and over time. A higher rate can partly reflect more reporting.</p></div>
    <div class="finding red"><h4>Exposure is not population</h4><p>Rates divide by where people live, not where they spend time. Someone who works, commutes or socializes in a high-assault area carries that exposure home to a different denominator.</p></div>
    <div class="finding red"><h4>Residential denominators</h4><p>Divisions with many visitors, workers or unhoused residents, Central above all, show inflated rates because victims there often do not live there.</p></div>
    <div class="finding"><h4>Who is counted</h4><p>{fmt(C["total"] - C["known"])} victims with unknown race or sex are left out of the rates. LAPD descent codes are officer-recorded and were collapsed to four groups; everyone else is excluded.</p></div>
    <div class="finding"><h4>Period and population mismatch</h4><p>Victims cover January 2020 to June 2023, a window that includes the pandemic. Population is the ACS 2020 to 2024 five-year average, with sampling error at the tract level.</p></div>
  </div>

  <div class="section-title">Method</div>
  <p class="note">LAPD victim descent codes mapped to four groups (Asian combines the Asian descent codes). Population by census tract from the ACS 2020 to 2024 five-year release via Census Reporter; {fmt(P["tracts"])} tracts inside the city were assigned to LAPD divisions by tract centroid using the city's division boundaries ({P["unassigned"]} fell outside). Rates divide victims by residents and by {D["years"]} years. Cells with fewer than {fmt(D["min_pop"])} residents are not rated.</p>
  <p class="note">Sources: LAPD Open Data (Crime Data from 2020 to Present), US Census Bureau ACS, LA GeoHub. Reproduce with <code>scripts/compute_rates.py</code> and <code>scripts/build_page.py</code>.</p>

</div>

<footer>
  <span>Assault victims in Los Angeles, Martin Ngoh</span>
  <a href="https://github.com/mngoh/LA-Crime">github.com/mngoh/LA-Crime</a>
  <a href="https://martinngoh.com">martinngoh.com</a>
</footer>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
  const C = {{ blue: '#2563eb', red: '#ef4444', text: '#f2f2f2', muted: '#8b8b8b', border: '#262626', surface: '#121212' }};
  Chart.defaults.color = C.muted; Chart.defaults.borderColor = C.border;
  Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'; Chart.defaults.font.size = 11;
  Object.assign(Chart.defaults.plugins.tooltip, {{ backgroundColor: C.surface, borderColor: C.border, borderWidth: 1, titleColor: C.text, bodyColor: C.muted }});
  Chart.defaults.plugins.legend.display = false; Chart.defaults.plugins.legend.labels.boxWidth = 12;
  const base = {{ responsive: true, maintainAspectRatio: false }};
  const bar = c => ({{ backgroundColor: 'transparent', borderColor: c, borderWidth: 1.5, borderRadius: 3, borderSkipped: false }});

  const RACES = {json.dumps(RACES)};
  const RATES = {json.dumps(R)};
  const SHARE = {{ simple: {json.dumps([share_simple[r] for r in RACES])}, aggravated: {json.dumps([share_agg[r] for r in RACES])} }};
  const DIV = {json.dumps(black_div)};
  const YEARS = {json.dumps(years)};
  const DIVMAP = {json.dumps(divmap)};

  new Chart(document.getElementById('rateChart'), {{
    type: 'bar',
    data: {{ labels: RACES, datasets: [
      {{ label: 'Women', data: RACES.map(r => RATES[r].F), ...bar(C.red) }},
      {{ label: 'Men', data: RACES.map(r => RATES[r].M), ...bar(C.blue) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.y.toLocaleString()}} per 100,000 per year` }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ title: {{ display: true, text: 'Victims per 100,000 per year' }} }} }} }}
  }});

  new Chart(document.getElementById('shareChart'), {{
    type: 'bar',
    data: {{ labels: RACES, datasets: [
      {{ label: 'Simple assault', data: SHARE.simple, ...bar(C.red) }},
      {{ label: 'Aggravated assault', data: SHARE.aggravated, ...bar(C.blue) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.y}}% women` }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ min: 0, max: 60, title: {{ display: true, text: 'Women as % of victims' }} }} }} }}
  }});

  new Chart(document.getElementById('divChart'), {{
    type: 'bar',
    data: {{ labels: DIV.map(d => d[0]), datasets: [{{ data: DIV.map(d => d[1]), ...bar(C.red) }}] }},
    options: {{ ...base, indexAxis: 'y',
      plugins: {{ tooltip: {{ callbacks: {{ label: i => {{ const d = DIV[i.dataIndex]; return `${{d[1].toLocaleString()}} per 100,000 (${{d[3].toLocaleString()}} victims, ${{d[4].toLocaleString()}} residents); men ${{d[2].toLocaleString()}}`; }} }} }} }},
      scales: {{ x: {{ title: {{ display: true, text: 'Black women assaulted per 100,000 per year' }} }}, y: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }} }} }}
  }});

  const yl = Object.keys(YEARS);
  new Chart(document.getElementById('yearChart'), {{
    type: 'bar',
    data: {{ labels: yl.map(y => y === '2023' ? '2023 (Jan to Jun)' : y), datasets: [
      {{ label: 'Women', data: yl.map(y => YEARS[y].F), ...bar(C.red) }},
      {{ label: 'Men', data: yl.map(y => YEARS[y].M), ...bar(C.blue) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ title: {{ display: true, text: 'Victims' }} }} }} }}
  }});

  const map = L.map('map', {{ zoomControl: true, scrollWheelZoom: false }}).setView([34.05, -118.35], 10);
  L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 16, className: 'dark-tiles'
  }}).addTo(map);
  const fmt = n => n == null ? 'n/a' : n.toLocaleString();
  DIVMAP.forEach(d => {{
    const b = d.rows.find(r => r.race === 'Black');
    const radius = 6 + Math.sqrt(d.rows.reduce((s, r) => s + r.F + r.M, 0)) / 6;
    const rows = d.rows.map(r => `<tr><td>${{r.race}}</td><td style="text-align:right">${{fmt(r.F)}}</td><td style="text-align:right">${{fmt(r.M)}}</td><td style="text-align:right">${{fmt(r.rateF)}}</td><td style="text-align:right">${{fmt(r.rateM)}}</td></tr>`).join('');
    L.circleMarker([d.lat, d.lon], {{ radius, color: C.red, weight: 1.5, fillColor: C.red, fillOpacity: 0.15 }}).addTo(map)
      .bindPopup(`<strong>${{d.name}}</strong><br><span style="color:#8b8b8b">Black women: ${{fmt(b.rateF)}} per 100,000 per year</span>
        <table><tr><th></th><th>Women</th><th>Men</th><th>Rate W</th><th>Rate M</th></tr>${{rows}}</table>
        <div style="color:#8b8b8b;margin-top:4px">Counts Jan 2020 to Jun 2023; rates per 100,000 residents per year</div>`);
  }});
</script>
</body>
</html>
'''
assert "—" not in html, "no em dashes on the page"
OUT.write_text(html)
print("wrote", OUT)
