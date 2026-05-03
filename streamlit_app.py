import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

st.set_page_config(
    page_title="Route Recommender — Mandi House to IFFCO Chowk",
    layout="wide",
    page_icon="🛣️"
)

st.markdown("""
<style>
.block-container { padding-top: 1.5rem }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
TOMTOM_KEY = "imAYgDRcFJmRBP4UKTdxWdgQp6LqZ9Rg"
ORIGIN     = "28.6270,77.2390"   # Mandi House
DEST       = "28.5290,77.0940"   # IFFCO Chowk

# Waypoints to force each route
WAYPOINTS = {
    "Route 1 — Sardar Patel Marg (SPM)": "28.5978,77.1842",
    "Route 2 — Rao Tularam Marg (RTR)":  "28.5770,77.1648",
}

ROUTE_COLORS = {
    "Route 1 — Sardar Patel Marg (SPM)": "#1A73E8",
    "Route 2 — Rao Tularam Marg (RTR)":  "#E8711A",
}

# ─────────────────────────────────────────────────────────────
# STATIC NETWORK DATA
# ─────────────────────────────────────────────────────────────
NETWORK = {
    "Route 1 — Sardar Patel Marg (SPM)": {
        "avg_lanes":          3.9,
        "avg_speed":          26.6,
        "std_dev_speed":      10.8,
        "signal_ratio":       0.53,
        "intersection_ratio": 0.72,
        "roadside_friction":  0.34,
        "merge_points":       4,
        "circularity":        1.15,
        "total_length_km":    18.5,
        "network_bt_min":     34.4,
        "bti_measured":       0.702,
        "unreliable":         "Junctions and merging zones",
        "color":              "#1A73E8",
    },
    "Route 2 — Rao Tularam Marg (RTR)": {
        "avg_lanes":          3.8,
        "avg_speed":          28.2,
        "std_dev_speed":      8.4,
        "signal_ratio":       0.44,
        "intersection_ratio": 0.78,
        "roadside_friction":  0.41,
        "merge_points":       3,
        "circularity":        1.45,
        "total_length_km":    20.1,
        "network_bt_min":     32.1,
        "bti_measured":       0.617,
        "unreliable":         "Road links and outer ring road merge",
        "color":              "#E8711A",
    },
}

# ─────────────────────────────────────────────────────────────
# FUZZY AHP WEIGHTS — Renormalised to 7 kept variables
# ─────────────────────────────────────────────────────────────
WEIGHTS = {
    "buffer_kept":      0.284,
    "commuter_type":    0.253,
    "buffer_time":      0.177,
    "route_following":  0.157,
    "trip_purpose":     0.111,
    "delay_threshold":  0.066,
    "occupation":       0.066,
}

# ─────────────────────────────────────────────────────────────
# TOMTOM — fetch live TT + route geometry
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)   # cache 5 minutes
def fetch_route(route_name):
    """Returns (travel_time_min, [(lat,lon), ...]) from TomTom."""
    via = WAYPOINTS[route_name]
    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{ORIGIN}:{via}:{DEST}/json"
        f"?key={TOMTOM_KEY}"
        f"&traffic=true"
        f"&travelMode=car"
        f"&routeType=fastest"
        f"&routeRepresentation=polyline"
    )
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        route = data["routes"][0]
        tt_min = round(route["summary"]["travelTimeInSeconds"] / 60, 1)
        # Extract polyline points
        points = route["legs"][0]["points"] + route["legs"][1]["points"]
        coords = [[p["latitude"], p["longitude"]] for p in points]
        return tt_min, coords
    except Exception:
        # Fallback coords if API fails
        fallback_coords = {
            "Route 1 — Sardar Patel Marg (SPM)": [
                [28.6270,77.2390],[28.6198,77.2165],[28.6045,77.1921],
                [28.5978,77.1842],[28.5788,77.1621],[28.5670,77.1430],
                [28.5480,77.1170],[28.5290,77.0940]
            ],
            "Route 2 — Rao Tularam Marg (RTR)": [
                [28.6270,77.2390],[28.6198,77.2165],[28.6045,77.1921],
                [28.5988,77.1855],[28.5770,77.1648],[28.5598,77.1488],
                [28.5420,77.1248],[28.5290,77.0940]
            ],
        }
        fallback_tt = {"Route 1 — Sardar Patel Marg (SPM)": 49.0,
                       "Route 2 — Rao Tularam Marg (RTR)":  52.0}
        return fallback_tt[route_name], fallback_coords[route_name]

# ─────────────────────────────────────────────────────────────
# BTI PREDICTION
# ─────────────────────────────────────────────────────────────
def predict_bti(r):
    return round(max(0.1, min(2.0,
        0.3641
        + 0.0411  * r["avg_lanes"]
        - 0.00308 * r["total_length_km"]
        - 0.01903 * r["avg_speed"]
        + 0.06103 * r["std_dev_speed"]
        + 0.03981 * r["intersection_ratio"]
        + 0.00618 * r["roadside_friction"]
    )), 4)

# ─────────────────────────────────────────────────────────────
# SCORING ENGINE — Fuzzy AHP weighted
# ─────────────────────────────────────────────────────────────
def score_route(route, user, tt):
    w  = WEIGHTS
    bti = route["bti_predicted"]
    bt  = round(bti * tt, 1)
    s   = {}

    # Buffer Kept (w=0.284)
    if user["buffer_kept"] == "Yes":
        s["buffer_kept"] = 1 - min(bt, 40) / 40
    else:
        s["buffer_kept"] = 1 - min(tt, 90) / 90

    # Commuter Type (w=0.253)
    if user["commuter_type"] == "Regular":
        s["commuter_type"] = 1 - min(bti, 1.5) / 1.5
    else:
        s["commuter_type"] = 1 - route["circularity"] / 2.0

    # Buffer Time (w=0.177)
    gap = user["buffer_time_min"] - bt
    s["buffer_time"] = max(0, min(1, (gap + 20) / 40))

    # Route Following (w=0.157)
    follow_map = {
        "Flexible — switches when needed": 0.8,
        "Partially follow":                0.5,
        "Habitual — stays on known route": 0.3,
    }
    fw = follow_map.get(user["route_following"], 0.5)
    s["route_following"] = fw * (1 - min(bti,1.5)/1.5) + \
                           (1-fw) * (1 - route["circularity"]/2.0)

    # Trip Purpose (w=0.111)
    purpose_map = {
        "Work":           0.7*(1-min(tt,90)/90) + 0.3*(1-min(bti,1.5)/1.5),
        "Education":      1 - min(bti, 1.5)/1.5,
        "Medical":        1 - min(tt, 90)/90,
        "Social/Leisure": 1 - route["circularity"]/2.0,
    }
    s["trip_purpose"] = purpose_map.get(user["trip_purpose"], 0.5)

    # Delay Threshold (w=0.066)
    thresh_map = {"1–2 min": 0.9, "2–5 min": 0.7,
                  "5–10 min": 0.4, "More than 10 min": 0.2}
    s["delay_threshold"] = thresh_map.get(user["delay_threshold"], 0.5) \
                           * (1 - min(bti,1.5)/1.5)

    # Occupation (w=0.066)
    occ_map = {
        "Working Professional":    0.6*(1-min(tt,90)/90) + 0.4*(1-min(bti,1.5)/1.5),
        "Cab / Commercial Driver": 1 - min(tt, 90)/90,
        "Student":                 1 - min(bti, 1.5)/1.5,
        "Self-employed":           1 - route["circularity"]/2.0,
        "Homemaker":               1 - route["circularity"]/2.0,
    }
    s["occupation"] = occ_map.get(user["occupation"], 0.5)

    total = sum(s[k] * w[k] for k in s)
    score = round(max(0, min(100, (total / sum(w.values())) * 100)))
    return score, s, bt

# ─────────────────────────────────────────────────────────────
# MAP
# ─────────────────────────────────────────────────────────────
def build_map(route_data, best_name=None):
    m = folium.Map(location=[28.585, 77.165],
                   zoom_start=12, tiles="CartoDB positron")

    for rname, (tt, coords) in route_data.items():
        color  = ROUTE_COLORS[rname]
        weight = 7 if rname == best_name else 3.5
        dash   = None if rname == best_name else "8 5"
        folium.PolyLine(
            coords, color=color, weight=weight,
            dash_array=dash, opacity=0.9,
            tooltip=f"{rname} — {tt} min"
        ).add_to(m)

    folium.Marker([28.6270, 77.2390],
        tooltip="Origin: Mandi House",
        icon=folium.Icon(color="green", icon="play", prefix="fa")
    ).add_to(m)

    folium.Marker([28.5290, 77.0940],
        tooltip="Destination: IFFCO Chowk",
        icon=folium.Icon(color="red", icon="stop", prefix="fa")
    ).add_to(m)

    return m

# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────
st.title("🛣️ Route Recommender")
st.caption("Mandi House → IFFCO Chowk  ·  Real-time TomTom Travel Time  ·  Fuzzy AHP Scoring")

# Initialise session state
if "results" not in st.session_state:
    st.session_state.results = None
if "route_data" not in st.session_state:
    st.session_state.route_data = None

col_form, col_map = st.columns([1, 1.6], gap="large")

with col_form:
    st.subheader("Your travel profile")

    commuter_type   = st.selectbox("Commuter type",
                        ["Regular", "Non-regular"])
    trip_purpose    = st.selectbox("Trip purpose",
                        ["Work", "Education", "Medical", "Social/Leisure"])
    occupation      = st.selectbox("Occupation",
                        ["Working Professional", "Cab / Commercial Driver",
                         "Student", "Self-employed", "Homemaker"])
    delay_threshold = st.selectbox("How much delay before you switch route?",
                        ["1–2 min", "2–5 min", "5–10 min", "More than 10 min"])
    route_following = st.selectbox("Route switching behaviour",
                        ["Flexible — switches when needed",
                         "Partially follow",
                         "Habitual — stays on known route"])
    buffer_kept     = st.selectbox("Do you keep buffer time before leaving?",
                        ["Yes", "No"])
    buffer_time_min = st.slider("How much buffer time? (min)", 0, 40, 15,
                        disabled=(buffer_kept == "No"))

    st.divider()
    run = st.button("🔍 Find best route", type="primary",
                    use_container_width=True)

# ─────────────────────────────────────────────────────────────
# FETCH ROUTE DATA (cached — only runs once per 5 min)
# ─────────────────────────────────────────────────────────────
if st.session_state.route_data is None:
    with st.spinner("Loading live route data from TomTom..."):
        route_data = {}
        for rname in NETWORK:
            tt, coords = fetch_route(rname)
            route_data[rname] = (tt, coords)
        st.session_state.route_data = route_data
else:
    route_data = st.session_state.route_data

# ─────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────
with col_map:
    st.subheader("Route map")

    # When button clicked — compute and store results in session state
    if run:
        user = {
            "commuter_type":   commuter_type,
            "trip_purpose":    trip_purpose,
            "occupation":      occupation,
            "delay_threshold": delay_threshold,
            "route_following": route_following,
            "buffer_kept":     buffer_kept,
            "buffer_time_min": buffer_time_min if buffer_kept=="Yes" else 0,
        }

        routes_scored = []
        for rname, rdata in NETWORK.items():
            tt, coords = route_data[rname]
            bti = predict_bti(rdata)
            entry = {**rdata, "name": rname,
                     "live_tt": tt, "bti_predicted": bti, "coords": coords}
            score, breakdown, bt = score_route(entry, user, tt)
            entry["score"]     = score
            entry["breakdown"] = breakdown
            entry["bt"]        = bt
            routes_scored.append(entry)

        routes_scored.sort(key=lambda x: x["score"], reverse=True)
        # Store in session state so results persist
        st.session_state.results = routes_scored

    # Show results if they exist in session state
    if st.session_state.results is None:
        m = build_map(route_data)
        st_folium(m, width=700, height=480)
        st.caption("Fill your travel profile and click **Find best route**.")

    else:
        routes_scored = st.session_state.results
        best = routes_scored[0]

        # Map with best route highlighted
        m = build_map(route_data, best["name"])
        st_folium(m, width=700, height=380)

        # Recommendation banner
        st.markdown(f"""
        <div style='background:#d4edda;border-radius:10px;
                    padding:14px 18px;margin-top:10px;margin-bottom:8px'>
          <div style='font-size:11px;font-weight:600;
                      color:#155724;margin-bottom:4px'>★ RECOMMENDED ROUTE</div>
          <div style='font-size:18px;font-weight:700;color:#155724'>
            {best["name"]}</div>
          <div style='font-size:13px;color:#1e7e34;margin-top:4px'>
            Score: {best["score"]}/100 &nbsp;|&nbsp;
            Live TT: {best["live_tt"]} min &nbsp;|&nbsp;
            Buffer demand: {best["bt"]} min &nbsp;|&nbsp;
            BTI: {best["bti_predicted"]}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Score bar chart
        st.subheader("Route comparison")
        fig = go.Figure(go.Bar(
            x=[r["name"].replace(" — ","\n") for r in routes_scored],
            y=[r["score"] for r in routes_scored],
            marker_color=[r["color"] for r in routes_scored],
            text=[f"{r['score']}/100" for r in routes_scored],
            textposition="outside",
        ))
        fig.update_layout(
            yaxis=dict(range=[0,115], title="Recommendation score"),
            plot_bgcolor="white", paper_bgcolor="white",
            height=260, margin=dict(t=10,b=50,l=40,r=20),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # Live TT metrics
        c1, c2 = st.columns(2)
        for col, r in zip([c1, c2], routes_scored):
            with col:
                st.metric(
                    label=r["name"].split("—")[0].strip(),
                    value=f"{r['live_tt']} min",
                    delta=f"BTI {r['bti_predicted']} · Buffer demand {r['bt']} min"
                )

        # Route detail cards
        st.subheader("Route details")
        det1, det2 = st.columns(2)
        for col, r in zip([det1, det2], routes_scored):
            with col:
                border = "2px solid #28a745" if r["name"]==best["name"] \
                         else "1px solid #dee2e6"
                st.markdown(f"""
                <div style='border:{border};border-radius:10px;padding:14px'>
                  <b>{r["name"].split("—")[0].strip()}</b><br>
                  <small style='color:#888'>{r["name"].split("—")[1].strip()
                    if "—" in r["name"] else ""}</small>
                  <hr style='margin:8px 0'>
                  <div style='font-size:12px;line-height:1.9'>
                  Score: <b>{r["score"]}/100</b><br>
                  Live travel time: <b>{r["live_tt"]} min</b><br>
                  BTI (predicted): <b>{r["bti_predicted"]}</b><br>
                  Network buffer demand: <b>{r["bt"]} min</b><br>
                  Length: <b>{r["total_length_km"]} km</b><br>
                  Avg speed: <b>{r["avg_speed"]} km/h</b><br>
                  Signals: <b>{round(r["signal_ratio"]*100)}%</b><br>
                  Merge points: <b>{r["merge_points"]}</b><br>
                  Circularity: <b>{r["circularity"]}</b><br>
                  Unreliable segment: <i>{r["unreliable"]}</i>
                  </div>
                </div>
                """, unsafe_allow_html=True)

        # Weight breakdown
        with st.expander("📊 How the score was calculated (Fuzzy AHP breakdown)"):
            bd     = best["breakdown"]
            labels = [k.replace("_"," ").title() for k in bd]
            contribs = [bd[k]*WEIGHTS[k]*100 for k in bd]
            fig2 = go.Figure(go.Bar(
                x=labels, y=contribs,
                marker_color="#1A73E8",
                text=[f"{c:.1f}" for c in contribs],
                textposition="outside",
            ))
            fig2.update_layout(
                yaxis_title="Weighted contribution (%)",
                xaxis_tickangle=-20,
                plot_bgcolor="white", paper_bgcolor="white",
                height=300, margin=dict(t=10,b=80,l=40,r=20),
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.caption("Weights source: Buckley Fuzzy AHP on 125 respondent survey data")
