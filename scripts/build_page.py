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

T = D["tests"]
M = json.loads((ROOT / "data" / "model_results.json").read_text())
N = json.loads((ROOT / "data" / "nibrs_comparison.json").read_text())
# LA city, ACS 2020 to 2024: Black alone or in combination (B02009) over Black alone (B02001)
BLACK_COMBO = 400482 / 323828
BLACK_COMBO_PCT = round((BLACK_COMBO - 1) * 100)
ladder = M["ladder"]; final = ladder[-1]; crude = ladder[0]
explained = round((1 - (final["rate_ratio"] - 1) / (crude["rate_ratio"] - 1)) * 100)
rr = {l["model"].split(" ")[0]: l["rate_ratio"] for l in ladder}
share = lambda a, b: round((rr[a] - rr[b]) / (crude["rate_ratio"] - 1) * 100)  # share of the crude excess removed by a step
loc_share, ses_share, age_share = share("M2", "M3"), share("M3", "M4"), share("M0", "M1")
loc_sorted = sorted([d for d in T["location"]["divisions"] if d["ratio"] is not None], key=lambda d: -d["ratio"])
other_pop_f = sum(P["city"][r]["F"] for r in RACES[1:])
other_women_rate = round(T["women_n"]["other"] / other_pop_f / D["years"] * 1e5)
std = T["age"]["standardized"]
home_black = round(sum(b for l, b in zip(T["premises"]["labels"], T["premises"]["black"]) if "Dwelling" in l), 1)
home_other = round(sum(o for l, o in zip(T["premises"]["labels"], T["premises"]["other"]) if "Dwelling" in l), 1)
wi = {k: i for i, k in enumerate(T["weapons"]["labels"])}
peak_band = T["age"]["labels"][max(range(len(T["age"]["labels"])), key=lambda i: T["age"]["rates"]["Black"][i] or 0)]

html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Assault victims in Los Angeles</title>
  <meta name="description" content="Black women in LA are assaulted at 3 to 6 times the rate of Hispanic and White women, and nothing we measured explains why. {fmt(C['total'])} LAPD assault reports, 2020 to 2023, as rates per 100,000 residents." />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{ --bg: #0a0a0a; --surface: #121212; --border: #262626; --text: #f2f2f2; --muted: #8b8b8b; --blue: #2563eb; --blue-light: #93c5fd; --red: #ef4444; }}
    body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.6; }}
    a {{ color: var(--blue-light); text-decoration: none; }} a:hover {{ text-decoration: underline; }}
    header {{ border-bottom: 1px solid var(--border); padding: 28px 40px; display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap; }}
    header h1 {{ font-size: 22px; font-weight: 600; letter-spacing: -0.3px; }}
    .lede {{ font-size: 21px; font-weight: 600; line-height: 1.4; letter-spacing: -0.2px; max-width: 860px; margin-bottom: 24px; }}
    @media (max-width: 640px) {{ .lede {{ font-size: 18px; }} }}
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

  <p class="lede">Black women in LA are assaulted at 3 to 6 times the rate of Hispanic and White women, and nothing we measured explains why.</p>

  <div class="answer">
    <div class="q">The question</div>
    <p>Black women are a far larger share of assault victims than women of any other group. Is that a higher rate of victimization, or just where assaults happen?</p>
    <p>A higher rate. Per 100,000 residents a year, Black women are assaulted {fmt(bw["F"])} times: {ratio["Hispanic"]} times the rate of Hispanic women, {ratio["White"]} times White women, {ratio["Asian"]} times Asian women, and more often than the men of any group, Black men included.</p>
    <p>Adjusted for age, year, where the assault happened, neighborhood poverty, income, unemployment, housing and homelessness, the gap is still about {round(M["pairwise"]["Hispanic"]["adjusted"]["rate_ratio"])} times Hispanic or White women and {round(M["pairwise"]["Asian"]["adjusted"]["rate_ratio"])} times Asian women. The model is below.</p>
  </div>

  <div class="section-title">Dataset</div>
  <div class="cards">
    <div class="card"><div class="label">Assaults</div><div class="value">{fmt(C["total"])}</div><div class="sub">reported Jan 2020 to Dec 2023</div></div>
    <div class="card"><div class="label">Simple assault</div><div class="value">{fmt(C["simple"])}</div><div class="sub">battery, incl. partner</div></div>
    <div class="card"><div class="label">Aggravated</div><div class="value">{fmt(C["aggravated"])}</div><div class="sub">weapon or serious injury</div></div>
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
      <div class="chart-sub">Victims with known sex.</div>
      <div class="chart-wrap tall"><canvas id="yearChart"></canvas></div>
    </div>
  </div>

  <div class="section-title">Findings</div>
  <div class="findings">
    <div class="finding red"><h4>The rate gap is real</h4><p>Black women's victimization rate is {fmt(bw["F"])} per 100,000 a year. Hispanic women: {fmt(R["Hispanic"]["F"])}. White women: {fmt(R["White"]["F"])}. Asian women: {fmt(R["Asian"]["F"])}. Population share does not explain it.</p></div>
    <div class="finding red"><h4>More often than men</h4><p>Black women are assaulted at {int(bw["ratio"]*100)}% of the rate of Black men. For Hispanic, White and Asian women the figure is {int(R["Hispanic"]["ratio"]*100)}%, {int(R["White"]["ratio"]*100)}% and {int(R["Asian"]["ratio"]*100)}%.</p></div>
    <div class="finding"><h4>Simple assault is where women outnumber men</h4><p>{share_simple["Black"]}% of Black simple-assault victims are women, the highest of any group ({min(share_simple[r] for r in RACES if r != "Black")}% to {max(share_simple[r] for r in RACES if r != "Black")}% elsewhere). In aggravated assault the share is {share_agg["Black"]}%, against {min(share_agg[r] for r in RACES if r != "Black")}% to {max(share_agg[r] for r in RACES if r != "Black")}% for other groups.</p></div>
    <div class="finding"><h4>South LA carries the counts, Central the rate</h4><p>77th Street ({fmt(by_div["77th Street"][3])}) and Southeast ({fmt(by_div["Southeast"][3])}) have the most Black female victims. Central has the highest rate ({fmt(black_div[0][1])}) on a small resident population.</p></div>
    <div class="finding"><h4>Mostly strong-arm</h4><p>{round(strong / C["total"] * 100)}% of all assaults involved hands, fists or feet rather than a weapon. Handguns appear in {fmt(weapons["HAND GUN"])}.</p></div>
    <div class="finding"><h4>What this does not show</h4><p>Why. These are reported assaults against residential population. The caveats below matter as much as the numbers.</p></div>
  </div>

  <div class="section-title">Map</div>
  <p class="note">Each marker is a division. Click one for counts and rates by race and sex.</p>
  <div id="map" class="section-end"></div>

  <div class="section-title">Testing explanations</div>
  <p class="note">Six cuts of the same data, women only ({fmt(T["women_n"]["black"])} Black women, {fmt(T["women_n"]["other"])} other women). Each asks whether a plain explanation accounts for the gap.</p>

  <div class="charts">
    <div class="chart-box">
      <h3>Age</h3>
      <div class="chart-sub">Does the gap survive comparing women of the same age? Yes. Standardized to one age mix, Black women's rate is {fmt(std["Black"])} against {fmt(std["Hispanic"])}, {fmt(std["White"])} and {fmt(std["Asian"])}. The curve peaks at ages {peak_band}.</div>
      <div class="chart-wrap"><canvas id="ageChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Location</h3>
      <div class="chart-sub">Is it where assaults happen? Partly. At other women's rate in each division, Black women would be at {fmt(T["location"]["expected_if_other_rates"])} per 100,000 instead of {fmt(T["location"]["actual_rate"])}. Inside every rated division their rate is still {round(loc_sorted[-1]["ratio"], 1)} to {round(loc_sorted[0]["ratio"], 1)} times other women's.</div>
      <div class="chart-wrap"><canvas id="locChart"></canvas></div>
    </div>
  </div>
  <div class="charts">
    <div class="chart-box">
      <h3>Type of assault</h3>
      <div class="chart-sub">Simple or aggravated? Both, and aggravated more: {round(T["type"]["simple"]["Black"] / T["type"]["simple"]["Hispanic"], 1)} times Hispanic women for simple assault, {round(T["type"]["aggravated"]["Black"] / T["type"]["aggravated"]["Hispanic"], 1)} times for aggravated.</div>
      <div class="chart-wrap"><canvas id="typeChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Time</h3>
      <div class="chart-sub">Does it persist? Every year. Black women: {", ".join(fmt(T["time"][y]["Black"]) for y in ["2020", "2021", "2022"])} and {fmt(T["time"]["2023"]["Black"])} per 100,000.</div>
      <div class="chart-wrap"><canvas id="timeChart"></canvas></div>
    </div>
  </div>
  <div class="charts section-end">
    <div class="chart-box">
      <h3>Premises</h3>
      <div class="chart-sub">Different places? Barely. At home {home_black}% vs {home_other}%, street {T["premises"]["black"][T["premises"]["labels"].index("Street")]}% vs {T["premises"]["other"][T["premises"]["labels"].index("Street")]}%. Share of each group's assaults, top eight premises.</div>
      <div class="chart-wrap tall"><canvas id="premChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Weapons</h3>
      <div class="chart-sub">Different circumstances? Yes. A firearm in {T["weapons"]["black"][wi["Firearm"]]}% of assaults on Black women against {T["weapons"]["other"][wi["Firearm"]]}% for other women; strong-arm {T["weapons"]["black"][wi["Strong-arm"]]}% vs {T["weapons"]["other"][wi["Strong-arm"]]}%.</div>
      <div class="chart-wrap tall"><canvas id="weapChart"></canvas></div>
    </div>
  </div>
  <div class="findings">
    <div class="finding red"><h4>Reporting: not testable here</h4><p>LAPD data holds only what was reported. The National Crime Victimization Survey measures unreported crime nationally, not for Los Angeles. If Black women report assaults more or less often than other women, every rate above moves, and this data cannot say which way.</p></div>
    <div class="finding red"><h4>What remains</h4><p>After age, location and year, a gap of roughly two and a half to three stands, widest in aggravated and armed assaults. The model below puts numbers on it. The data shows the gap; it does not explain it.</p></div>
  </div>

  <div class="section-title">The model</div>
  <p class="note">One question, answered one adjustment at a time: how much of the gap survives? Poisson rate models at the census-tract level, women only, {fmt(M["cells"])} tract by group by age by year cells, {M["coverage"]["Black"]}% of located Black women victims and {M["coverage"]["Other"]}% of other women (the rest were assaulted in tracts with no resident women of their group and age, so they have no denominator). Each bar is Black women's rate as a multiple of other women's after the controls named.</p>
  <div class="charts section-end">
    <div class="chart-box">
      <h3>Surviving rate ratio</h3>
      <div class="chart-sub">Crude {crude["rate_ratio"]}x. After age, year, where it happened and tract poverty, income, unemployment, renters and density: {final["rate_ratio"]}x (95% CI {final["ci_low"]} to {final["ci_high"]}). Controls account for about {explained}% of the excess; the rest stands.</div>
      <div class="chart-wrap"><canvas id="modelChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Fully adjusted, by assault type</h3>
      <div class="chart-sub">The same controls, run separately. Simple assault {M["fully_adjusted_by_type"]["simple"]["rate_ratio"]}x, aggravated assault {M["fully_adjusted_by_type"]["aggravated"]["rate_ratio"]}x. The serious end of the distribution is where the gap resists explanation.</div>
      <div class="chart-wrap"><canvas id="typeModelChart"></canvas></div>
    </div>
  </div>
  <div class="charts section-end">
    <div class="chart-box">
      <h3>Each comparison group on its own</h3>
      <div class="chart-sub">Pooling hides a spread. Fully adjusted, Black women's rate is {M["pairwise"]["Hispanic"]["adjusted"]["rate_ratio"]} times Hispanic women's, {M["pairwise"]["White"]["adjusted"]["rate_ratio"]} times White women's and {M["pairwise"]["Asian"]["adjusted"]["rate_ratio"]} times Asian women's. Crude gaps in grey outline.</div>
      <div class="chart-wrap"><canvas id="pairChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Does the homelessness measure matter?</h3>
      <div class="chart-sub">LAHSA publishes counts, not person estimates, by tract. Three definitions give the same answer: {", ".join(f"{v['rate_ratio']}x" for v in M["homelessness_sensitivity"].values())}. The covariate is not driving the result.</div>
      <div class="chart-wrap"><canvas id="sensChart"></canvas></div>
    </div>
  </div>
  <div class="findings">
    <div class="finding red"><h4>What the model says</h4><p>Where assaults happen is the biggest single factor, removing about {loc_share}% of the excess. Tract poverty, income, unemployment, renters and density together remove another {ses_share}% once location is in. Age removes {age_share}%; year, nothing. A {final["rate_ratio"]}-fold gap remains that none of these measured factors explain.</p></div>
    <div class="finding"><h4>What it cannot say</h4><p>Residents are the denominator, so exposure away from home is unmeasured, and {round(100 - M["coverage"]["Black"])}% of Black women victims were assaulted in tracts with no resident women like them. {"Homelessness enters only as a tract-level count from the 2024 LAHSA count, a proxy for exposure, not a measure of who the victims were." if M["homelessness_included"] else "Homelessness counts by tract are not in the model."} Reporting behavior is invisible to police data.</p></div>
  </div>

  <div class="section-title">A second records system, and intimate partner assault</div>
  <p class="note">LAPD moved to the FBI's NIBRS standard in March 2024, so {N["windows"]["nibrs"]} is a separate test on new records. Partner and non-partner assault are counted the same way in both systems, women only, per 100,000 residents a year. LAPD's old system codes intimate partner assault separately (626 and 236), which also lets it be split out.</p>
  <div class="charts section-end">
    <div class="chart-box">
      <h3>The gap replicates</h3>
      <div class="chart-sub">All assaults on women. Black women's rate is {N["ratios"]["nibrs"]["all"]["Hispanic"]} times Hispanic women's and {N["ratios"]["nibrs"]["all"]["White"]} times White women's in NIBRS, against {N["ratios"]["legacy"]["all"]["Hispanic"]} and {N["ratios"]["legacy"]["all"]["White"]} before. The Asian comparison moved most, from {N["ratios"]["legacy"]["all"]["Asian"]} to {N["ratios"]["nibrs"]["all"]["Asian"]}.</div>
      <div class="chart-wrap"><canvas id="nibrsChart"></canvas></div>
    </div>
    <div class="chart-box">
      <h3>Intimate partner assault</h3>
      <div class="chart-sub">Nearly half of all assaults on women in every group. Black women's partner assault rate is {fmt(N["rates"]["legacy"]["intimate"]["Black"])}, {N["ratios"]["legacy"]["intimate"]["Hispanic"]} times Hispanic and {N["ratios"]["legacy"]["intimate"]["White"]} times White women's. 2020 to 2023.</div>
      <div class="chart-wrap"><canvas id="ipvChart"></canvas></div>
    </div>
  </div>
  <div class="findings">
    <div class="finding red"><h4>Same gap, new system</h4><p>Different years, a different records system and different offense coding, and Black women's rate is still about 3 times Hispanic women's and 6 times White women's.</p></div>
    <div class="finding red"><h4>Not concentrated at home</h4><p>Intimate partner assault is {N["intimate_share"]["legacy"]["Black"]}% of assaults on Black women and {N["intimate_share"]["legacy"]["Hispanic"]}% for Hispanic women. The gap is the same size with partners as without.</p></div>
  </div>

  <p class="note">Context: this is the direction national evidence points. The National Crime Victimization Survey, which counts crimes whether or not they were reported, found the rate of violence against Black women almost 50% higher than against White women in 2005, by strangers, acquaintances and partners alike (<a href="https://bjs.ojp.gov/sites/g/files/xyckuh236/files/media/document/heimer.pdf">Heimer and colleagues, BJS</a>; <a href="https://bjs.ojp.gov/content/pub/pdf/bvvc.pdf">Harrell, BJS 2007</a>). Los Angeles's police-recorded gap is larger than that national survey figure, which is itself worth explaining.</p>

  <div class="section-title">Caveats</div>
  <div class="findings">
    <div class="finding red"><h4>This shows what, not why</h4><p>The data says Black women are assaulted at a higher rate. It does not say why. Nothing here measures causes, offenders or circumstances.</p></div>
    <div class="finding red"><h4>Reported crimes only</h4><p>Every number is a report that reached LAPD. Willingness to report, and police recording practice, differ by group, by area and over time. A higher rate can partly reflect more reporting.</p></div>
    <div class="finding red"><h4>Reports, not people</h4><p>Rates count assault reports. A woman assaulted twice counts twice, which is common in partner violence, so a rate of {fmt(bw["F"])} per 100,000 is not the share of Black women assaulted.</p></div>
    <div class="finding red"><h4>Who is recorded as Black</h4><p>Officers record victim race by sight; the population counts people who are Black alone. LA has {BLACK_COMBO_PCT}% more people who are Black alone or in combination with another race. If multiracial victims are recorded as Black, the rate is overstated by up to that much: at worst {round(ratio["Hispanic"] / BLACK_COMBO, 1)} times Hispanic women and {round(ratio["White"] / BLACK_COMBO, 1)} times White women instead of {ratio["Hispanic"]} and {ratio["White"]}.</p></div>
    <div class="finding red"><h4>Exposure is not population</h4><p>Rates divide by where people live, not where they spend time. Someone who works, commutes or socializes in a high-assault area carries that exposure home to a different denominator.</p></div>
    <div class="finding red"><h4>Residential denominators</h4><p>Divisions with many visitors, workers or unhoused residents, Central above all, show inflated rates because victims there often do not live there.</p></div>
    <div class="finding"><h4>Who is counted</h4><p>Simple and aggravated assault, including intimate partner assault (LAPD codes 624, 626, 230 and 236). Other assault codes (on police, child abuse, sexual battery) are left out. {fmt(C["total"] - C["known"])} victims with unknown race or sex are left out of the rates. LAPD descent codes are officer-recorded and were collapsed to four groups; everyone else is excluded.</p></div>
    <div class="finding"><h4>Period and population mismatch</h4><p>Victims cover January 2020 to December 2023, a window that includes the pandemic. Population is the ACS 2020 to 2024 five-year average, with sampling error at the tract level.</p></div>
  </div>

  <div class="section-title">Method</div>
  <p class="note">LAPD victim descent codes mapped to four groups (Asian combines the Asian descent codes). Population by census tract from the ACS 2020 to 2024 five-year release via Census Reporter; {fmt(P["tracts"])} tracts inside the city were assigned to LAPD divisions by tract centroid using the city's division boundaries ({P["unassigned"]} fell outside). Rates divide victims by residents and by {D["years"]} years. Cells with fewer than {fmt(D["min_pop"])} residents are not rated.</p>
  <p class="note">Sources: LAPD Open Data (Crime Data from 2020 to 2024; NIBRS Victims), US Census Bureau ACS, LA GeoHub, LAHSA. NIBRS assaults are offense codes 13A and 13B, classed as intimate partner by their offense label; officer and child victims are excluded in both systems. NIBRS labels do not map one-to-one to the old codes, so compare ratios between groups rather than levels between systems. Reproduce with the scripts in the repository.</p>

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
    data: {{ labels: yl, datasets: [
      {{ label: 'Women', data: yl.map(y => YEARS[y].F), ...bar(C.red) }},
      {{ label: 'Men', data: yl.map(y => YEARS[y].M), ...bar(C.blue) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ title: {{ display: true, text: 'Victims' }} }} }} }}
  }});

  const T = {json.dumps(T)};
  const line = (c, dash) => ({{ borderColor: c, backgroundColor: c, borderWidth: 1.5, pointRadius: 2.5, tension: 0.25, fill: false, borderDash: dash || [] }});
  const womenColor = {{ Black: C.red, Hispanic: C.blue, White: '#93c5fd', Asian: C.muted }};

  new Chart(document.getElementById('ageChart'), {{
    type: 'line',
    data: {{ labels: T.age.labels, datasets: RACES.map(r => ({{ label: r + ' women', data: T.age.rates[r], ...line(womenColor[r]), spanGaps: true }})) }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.y == null ? 'n/a' : i.parsed.y.toLocaleString()}} per 100,000 per year` }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, title: {{ display: true, text: 'Victim age' }} }}, y: {{ title: {{ display: true, text: 'Victims per 100,000 per year' }} }} }} }}
  }});

  const LOC = {json.dumps(loc_sorted)};
  new Chart(document.getElementById('locChart'), {{
    type: 'bar',
    data: {{ labels: LOC.map(d => d.division), datasets: [{{ data: LOC.map(d => d.ratio), ...bar(C.red) }}] }},
    options: {{ ...base, indexAxis: 'y',
      plugins: {{ tooltip: {{ callbacks: {{ label: i => {{ const d = LOC[i.dataIndex]; return `${{d.ratio}}x: Black women ${{d.black_rate.toLocaleString()}}, other women ${{d.other_rate.toLocaleString()}} per 100,000 per year`; }} }} }} }},
      scales: {{ x: {{ min: 0, title: {{ display: true, text: "Black women's rate as a multiple of other women's, same division" }} }}, y: {{ grid: {{ display: false }}, ticks: {{ color: C.text, font: {{ size: 10 }} }} }} }} }}
  }});

  new Chart(document.getElementById('typeChart'), {{
    type: 'bar',
    data: {{ labels: RACES, datasets: [
      {{ label: 'Simple assault', data: RACES.map(r => T.type.simple[r]), ...bar(C.red) }},
      {{ label: 'Aggravated assault', data: RACES.map(r => T.type.aggravated[r]), ...bar(C.blue) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.y.toLocaleString()}} per 100,000 women per year` }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ title: {{ display: true, text: 'Women victims per 100,000 per year' }} }} }} }}
  }});

  const TY = Object.keys(T.time);
  new Chart(document.getElementById('timeChart'), {{
    type: 'line',
    data: {{ labels: TY, datasets: RACES.map(r => ({{ label: r + ' women', data: TY.map(y => T.time[y][r]), ...line(womenColor[r]) }})) }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.y.toLocaleString()}} per 100,000 per year` }} }} }},
      scales: {{ x: {{ grid: {{ display: false }} }}, y: {{ min: 0, title: {{ display: true, text: 'Victims per 100,000 per year' }} }} }} }}
  }});

  const twoGroups = (id, src, xTitle) => new Chart(document.getElementById(id), {{
    type: 'bar',
    data: {{ labels: src.labels, datasets: [
      {{ label: 'Black women', data: src.black, ...bar(C.red) }},
      {{ label: 'Other women', data: src.other, ...bar(C.blue) }} ] }},
    options: {{ ...base, indexAxis: 'y', plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.x}}%` }} }} }},
      scales: {{ x: {{ min: 0, title: {{ display: true, text: xTitle }} }}, y: {{ grid: {{ display: false }}, ticks: {{ color: C.text, font: {{ size: 10 }} }} }} }} }}
  }});
  twoGroups('premChart', T.premises, "Share of the group's assaults (%)");
  twoGroups('weapChart', T.weapons, "Share of the group's assaults (%)");

  const LADDER = {json.dumps(ladder)};
  new Chart(document.getElementById('modelChart'), {{
    type: 'bar',
    data: {{ labels: LADDER.map(l => l.model.replace(/^M\\d /, '')), datasets: [{{ data: LADDER.map(l => l.rate_ratio), ...bar(C.red) }}] }},
    options: {{ ...base, indexAxis: 'y',
      plugins: {{ tooltip: {{ callbacks: {{ label: i => {{ const l = LADDER[i.dataIndex]; return `${{l.rate_ratio}}x (95% CI ${{l.ci_low}} to ${{l.ci_high}})`; }} }} }} }},
      scales: {{ x: {{ min: 0, title: {{ display: true, text: "Black women's rate as a multiple of other women's" }} }}, y: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }} }} }}
  }});
  const BT = {json.dumps(M["fully_adjusted_by_type"])};
  new Chart(document.getElementById('typeModelChart'), {{
    type: 'bar',
    data: {{ labels: ['Simple assault', 'Aggravated assault'], datasets: [{{ data: [BT.simple.rate_ratio, BT.aggravated.rate_ratio], ...bar(C.red), maxBarThickness: 70 }}] }},
    options: {{ ...base, plugins: {{ tooltip: {{ callbacks: {{ label: i => {{ const k = i.dataIndex ? BT.aggravated : BT.simple; return `${{k.rate_ratio}}x (95% CI ${{k.ci_low}} to ${{k.ci_high}})`; }} }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ min: 0, title: {{ display: true, text: 'Adjusted rate ratio' }} }} }} }}
  }});

  const PAIR = {json.dumps(M["pairwise"])};
  const pairLabels = Object.keys(PAIR).map(k => k + ' women');
  new Chart(document.getElementById('pairChart'), {{
    type: 'bar',
    data: {{ labels: pairLabels, datasets: [
      {{ label: 'Crude', data: Object.values(PAIR).map(p => p.crude.rate_ratio), ...bar(C.muted) }},
      {{ label: 'Fully adjusted', data: Object.values(PAIR).map(p => p.adjusted.rate_ratio), ...bar(C.red) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => {{ const p = Object.values(PAIR)[i.dataIndex][i.datasetIndex ? 'adjusted' : 'crude']; return `${{i.dataset.label}}: ${{p.rate_ratio}}x (95% CI ${{p.ci_low}} to ${{p.ci_high}})`; }} }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ min: 0, title: {{ display: true, text: "Black women's rate as a multiple of the group's" }} }} }} }}
  }});
  const NB = {json.dumps(N)};
  const others = ['Hispanic', 'White', 'Asian'];
  new Chart(document.getElementById('nibrsChart'), {{
    type: 'bar',
    data: {{ labels: others.map(r => r + ' women'), datasets: [
      {{ label: 'Old system, 2020 to 2023', data: others.map(r => NB.ratios.legacy.all[r]), ...bar(C.muted) }},
      {{ label: 'NIBRS, 2024 to 2026', data: others.map(r => NB.ratios.nibrs.all[r]), ...bar(C.red) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.y}}x` }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ min: 0, title: {{ display: true, text: "Black women's rate as a multiple of the group's" }} }} }} }}
  }});
  new Chart(document.getElementById('ipvChart'), {{
    type: 'bar',
    data: {{ labels: RACES, datasets: [
      {{ label: 'Other assault', data: RACES.map(r => NB.rates.legacy.general[r]), ...bar(C.red) }},
      {{ label: 'Intimate partner', data: RACES.map(r => NB.rates.legacy.intimate[r]), ...bar(C.blue) }} ] }},
    options: {{ ...base, plugins: {{ legend: {{ display: true }}, tooltip: {{ callbacks: {{ label: i => `${{i.dataset.label}}: ${{i.parsed.y.toLocaleString()}} per 100,000 per year` }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ min: 0, title: {{ display: true, text: 'Women assaulted per 100,000 per year' }} }} }} }}
  }});
  const SENS = {json.dumps(M["homelessness_sensitivity"])};
  const sensNames = {{ homeless: 'People + one per dwelling', people_only: 'People counted only', unsheltered: 'Unsheltered only' }};
  new Chart(document.getElementById('sensChart'), {{
    type: 'bar',
    data: {{ labels: Object.keys(SENS).map(k => sensNames[k] || k), datasets: [{{ data: Object.values(SENS).map(v => v.rate_ratio), ...bar(C.red), maxBarThickness: 70 }}] }},
    options: {{ ...base, plugins: {{ tooltip: {{ callbacks: {{ label: i => {{ const v = Object.values(SENS)[i.dataIndex]; return `${{v.rate_ratio}}x (95% CI ${{v.ci_low}} to ${{v.ci_high}})`; }} }} }} }},
      scales: {{ x: {{ grid: {{ display: false }}, ticks: {{ color: C.text }} }}, y: {{ min: 0, max: 3.5, title: {{ display: true, text: 'Adjusted rate ratio, other women' }} }} }} }}
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
        <div style="color:#8b8b8b;margin-top:4px">Counts Jan 2020 to Dec 2023; rates per 100,000 residents per year</div>`);
  }});
</script>
</body>
</html>
'''
assert "—" not in html, "no em dashes on the page"
OUT.write_text(html)
print("wrote", OUT)
