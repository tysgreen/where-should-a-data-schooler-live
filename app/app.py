"""Where should a Data Schooler live?

    streamlit run app/app.py

Reads the one table the pipeline produces (data/marts/stations.parquet) and
ranks London stations using the priorities chosen at the top of the page.
"""
from pathlib import Path

import html

import pandas as pd
import pydeck as pdk
import streamlit as st

MART = Path(__file__).parent.parent / "data" / "marts" / "stations.parquet"
OFFICE = {"name": "The Data School, 25 Watling Street", "lat": 51.513016, "lon": -0.093946}

# The five themes: (label in the app, score column, one-line explanation)
THEMES = [
    ("Short commute", "score_commute", "door-to-desk time to Watling Street, arriving 9am"),
    ("Low rent", "score_rent", "median rent for a room in a shared home, by borough (ONS)"),
    ("Safety", "score_safety", "crimes against people within 500m, per month"),
    ("Things to do", "score_amenities", "pubs, cafés, gyms and supermarkets within 500m"),
    ("Green space", "score_green", "distance to the nearest park"),
]

# Sequential blue ramp (light = low score, dark = high score)
RAMP = ["#b7d3f6", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]

# Map legend: small drawn symbols matching the map, each with a short label
_DOT = '<svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="{}" stroke="white" stroke-width="1"/></svg>'
_RING = '<svg width="16" height="16"><circle cx="8" cy="8" r="6" fill="none" stroke="#0d366b" stroke-width="2.5"/></svg>'
_ITEM = '<span style="display:inline-flex;align-items:center;gap:6px;margin-right:18px">{}<span>{}</span></span>'
MAP_LEGEND = (
    '<div style="font-size:0.85rem;color:#555;display:flex;flex-wrap:wrap;align-items:center">'
    + _ITEM.format(_DOT.format(RAMP[0]) + _DOT.format(RAMP[3]) + _DOT.format(RAMP[-1]), "Station (darker = better match)")
    + _ITEM.format(_RING, "Your top pick")
    + _ITEM.format(_DOT.format("#eb6834"), "The Data School")
    + "</div>"
)


@st.cache_data
def load() -> pd.DataFrame:
    return pd.read_parquet(MART)


def colour_for(score: float) -> list[int]:
    hex_ = RAMP[min(int(score / 100 * len(RAMP)), len(RAMP) - 1)]
    return [int(hex_[i:i + 2], 16) for i in (1, 3, 5)] + [220]


def weighted_score(df: pd.DataFrame, weights: dict[str, int]) -> pd.Series:
    """Weighted average of the theme scores (each 0-100, higher = better)."""
    total = sum(weights.values()) or 1
    return sum(df[col] * w for col, w in weights.items()) / total


st.set_page_config(page_title="Where should a Data Schooler live?", page_icon="🏠",
                   layout="wide", initial_sidebar_state="collapsed")
df = load()

st.markdown(f"""
<style>
  .hero {{background: linear-gradient(135deg, {RAMP[-1]} 0%, {RAMP[3]} 100%); color: #fff;
          padding: 28px 32px 26px; border-radius: 18px; margin-bottom: 18px;}}
  .hero .kicker {{font-size: .78rem; letter-spacing: .14em; text-transform: uppercase; opacity: .8;}}
  .hero h1 {{color: #fff; font-size: 2.3rem; margin: 4px 0 6px; padding: 0;}}
  .hero p {{margin: 0; opacity: .92; font-size: 1.02rem; max-width: 760px;}}
  .pick {{border: 1px solid rgba(128,128,128,.25); border-radius: 16px; padding: 18px 20px; height: 100%;}}
  .pick.first {{border: 2px solid {RAMP[-1]}; box-shadow: 0 6px 18px rgba(16,66,129,.12);}}
  .pick .top {{display: flex; align-items: center; gap: 12px; min-height: 72px;}}
  .pick .rank {{width: 38px; height: 38px; border-radius: 50%; color: #fff; font-weight: 700;
                display: flex; align-items: center; justify-content: center; flex-shrink: 0;}}
  .pick .name {{font-size: 1.25rem; font-weight: 700; line-height: 1.2;}}
  .pick .sub {{font-size: .82rem; opacity: .65;}}
  .pick .score {{margin: 14px 0 12px; font-size: .85rem;}}
  .pick .score b {{font-size: 2rem; color: {RAMP[4]}; margin-right: 4px;}}
  .pick .score span, .pick .stats span {{opacity: .65;}}
  .pick .bar {{height: 6px; border-radius: 3px; background: rgba(128,128,128,.18); margin-bottom: 14px;}}
  .pick .bar span {{display: block; height: 100%; border-radius: 3px; background: {RAMP[3]};}}
  .pick .stats {{display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px;}}
  .pick .stats div {{font-size: .78rem;}}
  .pick .stats strong {{display: block; font-size: 1.05rem;}}
</style>
<div class="hero">
  <div class="kicker">The Data School · 25 Watling Street, London</div>
  <h1>Where should a Data Schooler live?</h1>
  <p>Tell us what matters to you, and we'll rank every tube, DLR, Overground and
     Elizabeth line station in London for life on the Data School commute.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- controls
LEVELS = [0, 1, 2, 3, 4, 5]
with st.container(border=True):
    st.markdown("**What matters to you?**  \n"
                "<span style='font-size:.85rem;opacity:.65'>Off = ignore it, 5 = really important</span>",
                unsafe_allow_html=True)
    weights = {}
    grid = st.columns(3) + st.columns(3)  # two rows of three, so every 0-5 control fits
    for col_ui, (label, col, help_text) in zip(grid, THEMES):
        with col_ui:
            choice_ = st.segmented_control(label, LEVELS, default=3, key=col, help=help_text,
                                           format_func=lambda n: "Off" if n == 0 else str(n))
            weights[col] = choice_ or 0  # clicking the selected option clears it -> treat as Off

    st.markdown("**Deal-breakers**")
    d1, d2 = st.columns(2)
    max_commute = d1.slider("Longest commute (minutes)", 10, int(df.commute_min.max()), 45, step=5)
    max_rent = d2.slider("Highest room rent (£/month)", 600, int(df.room_rent_gbp.max()), 900, step=25)

# ---------------------------------------------------------------- scoring
active = {col: w for col, w in weights.items() if w > 0}
ranked = df.copy()
# A station can only be scored on themes it has data for. The City of London has
# no ONS rent figure, so those stations drop out while "Low rent" matters to you.
missing = ranked[list(active)].isna().any(axis=1)
dropped_for_missing = int(missing.sum())
ranked = ranked[~missing]
ranked = ranked[(ranked.commute_min <= max_commute)
                & (ranked.room_rent_gbp.isna() | (ranked.room_rent_gbp <= max_rent))]
ranked["score"] = weighted_score(ranked, active).round() if active else 0
ranked = ranked.sort_values("score", ascending=False).reset_index(drop=True)
ranked.index += 1

note = (f" · {dropped_for_missing} hidden for missing data (the ONS publishes no rent for the City of London)"
        if dropped_for_missing else "")
st.caption(f"**{len(ranked)} of {len(df)} stations** match your deal-breakers{note}")

if ranked.empty:
    st.warning("No stations match - try a longer commute or a higher rent limit.")
    st.stop()

best_tab, map_tab, explore_tab, about_tab = st.tabs([
    ":material/emoji_events: Best matches", ":material/map: Map",
    ":material/search: Explore a station", ":material/info: About the data",
])


def pick_card(rank: int, r: pd.Series) -> str:
    """HTML for one of the top-3 cards."""
    rent = f"£{r.room_rent_gbp:,.0f}" if pd.notna(r.room_rent_gbp) else "n/a"
    return f"""
<div class="pick{' first' if rank == 1 else ''}">
  <div class="top">
    <div class="rank" style="background:{RAMP[-rank]}">{rank}</div>
    <div><div class="name">{html.escape(r.station_name)}</div>
         <div class="sub">{html.escape(str(r.borough_name))} · Zone {r.fare_zone}</div></div>
  </div>
  <div class="score"><b>{r.score:.0f}</b><span>/ 100 match</span></div>
  <div class="bar"><span style="width:{r.score:.0f}%"></span></div>
  <div class="stats">
    <div><span>Commute</span><strong>{r.commute_min:.0f} min</strong></div>
    <div><span>Room rent</span><strong>{rent}</strong></div>
    <div><span>Crime nearby</span><strong>{r.personal_crimes_per_month:.0f} / mo</strong></div>
    <div><span>Places nearby</span><strong>{r.amenities_total:.0f}</strong></div>
  </div>
</div>"""


# ---------------------------------------------------------------- best matches
with best_tab:
    for rank, col_ui in zip(range(1, 4), st.columns(3)):
        if rank <= len(ranked):
            col_ui.markdown(pick_card(rank, ranked.loc[rank]), unsafe_allow_html=True)

    if len(ranked) > 3:
        st.markdown("#### Also worth a look")
        rest = ranked.loc[4:10, ["station_name", "score", "commute_min", "room_rent_gbp",
                                 "personal_crimes_per_month", "amenities_total"]]
        st.dataframe(
            rest, use_container_width=True,
            column_config={
                "station_name": "Station",
                "score": st.column_config.ProgressColumn("Match", min_value=0, max_value=100, format="%d"),
                "commute_min": st.column_config.NumberColumn("Commute", format="%d min"),
                "room_rent_gbp": st.column_config.NumberColumn("Room rent", format="£%d"),
                "personal_crimes_per_month": st.column_config.NumberColumn("Crime / mo", format="%d"),
                "amenities_total": st.column_config.NumberColumn("Places nearby", format="%d"),
            },
        )

# ---------------------------------------------------------------- helpers for station details
MODE_NAMES = {"tube": "Tube", "dlr": "DLR", "overground": "Overground", "elizabeth-line": "Elizabeth line",
              "national-rail": "National Rail", "bus": "Bus", "tram": "Tram", "cable-car": "Cable car"}


def pretty_route(route_modes: str) -> str:
    """'tube > bus' -> 'Tube → Bus'"""
    if not route_modes:
        return "Walk"
    return " → ".join(MODE_NAMES.get(m, m.title()) for m in route_modes.split(" > "))


def vs_median(value, median, unit="", lower_is_better=True):
    """Delta text + colour for st.metric, comparing a station to the London median."""
    if pd.isna(value):
        return None, "off"
    diff = value - median
    if round(diff) == 0:
        return "same as London median", "off"
    return f"{diff:+,.0f}{unit} vs London median", ("inverse" if lower_is_better else "normal")


# ---------------------------------------------------------------- map
def station_tiles(s: pd.Series) -> None:
    """Three compact tiles about one station, stacked - shown beside the map."""
    rank_of = int(ranked.index[ranked.station_key == s.station_key][0])
    st.markdown(f"#### {s.station_name}")
    st.caption(f"#{rank_of} of {len(ranked)}  ·  {s.score:.0f}/100 match  ·  {s.borough_name}  ·  Zone {s.fare_zone}")

    with st.container(border=True):
        st.markdown("**:material/train: Getting to the Data School**")
        changes = "direct" if s.changes == 0 else f"{int(s.changes)} change" + ("s" if s.changes > 1 else "")
        st.metric("Door to desk", f"{s.commute_min:.0f} min")
        st.caption(f"{pretty_route(s.route_modes)}  ·  {changes}  ·  £{s.peak_fare_gbp:.2f} peak")

    with st.container(border=True):
        st.markdown("**:material/home: Living there**")
        a, b = st.columns(2)
        a.metric("Room rent", f"£{s.room_rent_gbp:,.0f}" if pd.notna(s.room_rent_gbp) else "n/a")
        b.metric("Crime / month", f"{s.personal_crimes_per_month:.0f}")

    with st.container(border=True):
        st.markdown("**:material/local_cafe: Within a 6-minute walk**")
        park = f"{s.nearest_park_m:,.0f} m" if s.nearest_park_m > 0 else "here"
        st.markdown(f"{s.pubs} pubs  ·  {s.cafes} cafés  ·  {s.gyms} gyms  ·  "
                    f"{s.supermarkets} supermarkets  \nNearest park: **{park}**")


with map_tab:
    # Which station (if any) did the user click? Streamlit keeps the map's selection
    # in session state under its key, so we can read it before drawing the layout.
    clicked = (st.session_state.get("station_map") or {}).get("selection", {}).get("objects", {}).get("stations", [])
    selected = ranked[ranked.station_key == clicked[0]["station_key"]] if clicked else ranked.iloc[0:0]

    map_df = ranked.assign(colour=ranked.score.map(colour_for), rank=ranked.index)
    stations_layer = pdk.Layer(
        "ScatterplotLayer", id="stations", data=map_df, get_position="[lon, lat]", get_fill_color="colour",
        get_radius=260, radius_min_pixels=4, radius_max_pixels=14, pickable=True, auto_highlight=True,
        stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1,
    )
    office_layer = pdk.Layer(
        "ScatterplotLayer", id="office", data=pd.DataFrame([OFFICE]), get_position="[lon, lat]",
        get_fill_color=[235, 104, 52, 255], get_radius=320, radius_min_pixels=7,
        stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2,
    )
    # Highlight the top pick with a dark ring around its dot
    top_ring_layer = pdk.Layer(
        "ScatterplotLayer", id="top_pick", data=map_df.head(1), get_position="[lon, lat]", filled=False,
        stroked=True, get_radius=700, radius_min_pixels=14, get_line_color=[13, 54, 107, 255],
        line_width_min_pixels=3,
    )
    # A soft blue halo behind the station that's been clicked
    selected_layer = pdk.Layer(
        "ScatterplotLayer", id="selected", data=selected, get_position="[lon, lat]",
        get_fill_color=[42, 120, 214, 70], get_radius=900, radius_min_pixels=18,
    )
    deck = pdk.Deck(
        layers=[selected_layer, stations_layer, office_layer, top_ring_layer],
        initial_view_state=pdk.ViewState(latitude=51.51, longitude=-0.11, zoom=9.8),
        tooltip={"html": "<b>#{rank} {station_name}</b><br/>Score {score} · {commute_min} min commute"
                         "<br/>{borough_name} · zone {fare_zone}"},
        map_style=None,
    )

    # Nothing selected: the map fills the width. Station selected: map shrinks left, tiles on the right.
    map_area, side = st.columns([2, 1]) if not selected.empty else (st.container(), None)
    with map_area:
        st.pydeck_chart(deck, height=600, key="station_map", on_select="rerun", selection_mode="single-object")
        st.markdown(MAP_LEGEND, unsafe_allow_html=True)
        st.caption("Click a station to see its details. The × above the map clears it.")
    if side is not None:
        with side:
            station_tiles(selected.iloc[0])

with explore_tab:
    choice = st.selectbox("Pick any station (ordered by how well it matches)", ranked.station_name, index=0)
    s = ranked[ranked.station_name == choice].iloc[0]
    med = df.median(numeric_only=True)
    rank_of = int(ranked.index[ranked.station_name == choice][0])

    st.markdown(f"### {choice}")
    st.caption(f"#{rank_of} of {len(ranked)}  ·  {s.score:.0f}/100 match  ·  "
               f"{s.borough_name}  ·  Zone {s.fare_zone}  ·  {s.lines}")

    CARD_HEIGHT = 380  # same fixed height so the three cards line up
    travel, living, nearby = st.columns(3)

    with travel.container(border=True, height=CARD_HEIGHT):
        st.markdown("**:material/train: Getting to the Data School**")
        d, c = vs_median(s.commute_min, med.commute_min, " min")
        st.metric("Door to desk, arriving 9am", f"{s.commute_min:.0f} min", d, delta_color=c)
        changes = "Direct" if s.changes == 0 else f"{int(s.changes)} change" + ("s" if s.changes > 1 else "")
        st.markdown(f"**Route:** {pretty_route(s.route_modes)}  \n**Changes:** {changes}  \n"
                    f"**Peak fare:** £{s.peak_fare_gbp:.2f} each way")

    with living.container(border=True, height=CARD_HEIGHT):
        st.markdown("**:material/home: Living there**")
        d, c = vs_median(s.room_rent_gbp, med.room_rent_gbp)
        st.metric("Room in a shared home",
                  f"£{s.room_rent_gbp:,.0f} / month" if pd.notna(s.room_rent_gbp) else "No data", d, delta_color=c,
                  help=f"Based on {s.room_rent_sample:.0f} room rents recorded in {s.borough_name}, "
                       f"{s.room_rent_period}. Whole 1-bed flat: £{s.rent_1bed_gbp:,.0f}."
                  if pd.notna(s.room_rent_gbp) else None)
        d, c = vs_median(s.personal_crimes_per_month, med.personal_crimes_per_month)
        st.metric("Crimes against people within 500m", f"{s.personal_crimes_per_month:.0f} / month", d, delta_color=c)

    with nearby.container(border=True, height=CARD_HEIGHT):
        st.markdown("**:material/local_cafe: Within a 6-minute walk**")
        park = f"{s.nearest_park_m:,.0f} m away" if s.nearest_park_m > 0 else "Right here"
        st.markdown(f"""
| Place | Count |
|:--|--:|
| Pubs | **{s.pubs}** |
| Cafés | **{s.cafes}** |
| Gyms | **{s.gyms}** |
| Supermarkets | **{s.supermarkets}** |
| Nearest park | **{park}** |
""")

# ---------------------------------------------------------------- about
with about_tab:
    st.markdown(f"""
- **Commute**: TfL Journey Planner, fastest route arriving 9am on a Tuesday.
- **Rent**: median rent for a room in a shared home, by borough, {df.room_rent_period.dropna().iloc[0]} (ONS *Private rental market in London*). Borough-level only, so every station in a borough shares a figure, and some boroughs are based on as few as 10 recorded rents. Hover the ⓘ on a station's rent for its sample size.
- **Crime**: police.uk street-level crime within 500m, averaged over {df.crime_period.iloc[0]}. "Crimes against people" = violence, robbery, theft from the person, burglary and weapons offences.
- **Places nearby**: OpenStreetMap, within 500m.
- **Scores**: each theme is ranked 0-100 across all stations (100 = best); your priorities set how much each counts.

Source code and pipeline: see the project README.
""")
