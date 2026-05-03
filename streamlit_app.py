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
.metric-card {
    background: #f8f9fa; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 8px
}
.best-badge {
    background: #d4edda; color: #155724;
    padding: 4px 12px; border-radius: 6px;
    font-size: 13px; font-weight: 600;
    display: inline-block; margin-bottom: 8px
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# TOMTOM API KEY
# ─────────────────────────────────────────────────────────────
TOMTOM_KEY = "imAYgDRcFJmRBP4UKTdxWdgQp6LqZ9Rg"

# ─────────────────────────────────────────────────────────────
# ROUTE COORDINATES — Properly traced road paths
# ─────────────────────────────────────────────────────────────
ROUTE_COORDS = {
    "Route 1 — Sardar Patel Marg (SPM)": [
        [28.6270, 77.2390],  # Mandi House
        [28.6238, 77.2282],  # Copernicus Marg / KG Marg junction
        [28.6198, 77.2165],  # Udyog Bhawan
        [28.6155, 77.2072],  # Willingdon Crescent
        [28.6103, 77.1989],  # Teen Murti Marg
        [28.6045, 77.1921],  # Sardar Patel Marg start
        [28.5978, 77.1842],  # Sardar Patel Marg mid
        [28.5912, 77.1768],  # Malcha Marg junction
        [28.5848, 77.1695],  # Satya Marg junction
        [28.5788, 77.1621],  # Dhaula Kuan flyover
        [28.5742, 77.1548],  # NH-48 entry
        [28.5670, 77.1430],  # NH-48 towards Aerocity
        [28.5590, 77.1305],  # Aerocity area
        [28.5480, 77.1170],  # Sheetla Mata Rd
        [28.5380, 77.1030],  # Approaching IFFCO
        [28.5290, 77.0940],  # IFFCO Chowk
    ],
    "Route 2 — Rao Tularam Marg (RTR)": [
        [28.6270, 77.2390],  # Mandi House
        [28.6238, 77.2282],  # Copernicus Marg
        [28.6198, 77.2165],  # Udyog Bhawan
        [28.6103, 77.1989],  # Teen Murti Marg
        [28.6045, 77.1921],  # Shantipath Circle
        [28.5988, 77.1855],  # Satya Marg
        [28.5922, 77.1792],  # Mahatma Gandhi Marg
        [28.5848, 77.1720],  # HareKrishna Marg
        [28.5770, 77.1648],  # Rao Tularam Marg start
        [28.5688, 77.1572],  # Benito Juarez Marg
        [28.5598, 77.1488],  # St. Mary's Road
        [28.5505, 77.1390],  # Outer Ring Road entry
        [28.5420, 77.1248],  # Towards Dwarka Expressway
        [28.5350, 77.1095],  # Gurgaon approach
        [28.5290, 77.0940],  # IFFCO Chowk
    ],
}

ROUTE_COLORS = {
    "Route 1 — Sardar Patel Marg (SPM)": "#1A73E8",
    "Route 2 — Rao Tularam Marg (RTR)":  "#E8711A",
}

# Waypoints to force TomTom to follow each specific route
ROUTE_WAYPOINTS = {
    "Route 1 — Sardar Patel Marg (SPM)": "28.5978,77.1842",  # SPM midpoint
    "Route 2 — Rao Tularam Marg (RTR)":  "28.5770,77.1648",  # RTR midpoint
}

# ─────────────────────────────────────────────────────────────
# NETWORK STATS (static — from your link data)
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
# FUZZY AHP WEIGHTS (from your Buckley Fuzzy AHP analysis)
# ─────────────────────────────────────────────────────────────
FAHP_WEIGHTS = {
    "buffer_kept":       0.1691,  # F3 — highest weight
    "commuter_type":     0.1510,  # F1
    "buffer_time":       0.1056,  # F2
    "travel_freq":       0.1001,  # F1
    "route_following":   0.0935,  # F3
    "nav_app":           0.0667,  # F2
    "trip_purpose":      0.0660,  # F4
    "corridor":          0.0622,  # F1
    "delay_threshold":   0.0393,  # F2
    "occupation":        0.0391,  # F4
    "avg_tt":            0.0380,  # F1
    "time_bands":        0.0239,  # F1
    "when_app":          0.0234,  # F2
    "unreliable_seg":    0.0220,  # F4
}

# ─────────────────────────────────────────────────────────────
# TOMTOM LIVE TRAVEL TIME
# ─────────────────────────────────────────────────────────────
def get_live_tt(route_name):
    """Fetch live travel time from TomTom for a specific route using waypoint."""
    origin = "28.6270,77.2390"
    dest   = "28.5290,77.0940"
    via    = ROUTE_WAYPOINTS[route_name]

    url = (
        f"https://api.tomtom.com/routing/1/calculateRoute/"
        f"{origin}:{via}:{dest}/json"
        f"?key={TOMTOM_KEY}"
        f"&traffic=true"
        f"&travelMode=car"
        f"&routeType=fastest"
    )

    try:
        resp = requests.get(url, timeout=8)
        data = resp.json()
        tt_seconds = data["routes"][0]["summary"]["travelTimeInSeconds"]
        tt_minutes = round(tt_seconds / 60, 1)
        return tt_minutes
    except Exception:
        # Fallback to static avg TT if API fails
        fallback = {
            "Route 1 — Sardar Patel Marg (SPM)": 49.0,
            "Route 2 — Rao Tularam Marg (RTR)":  52.0,
        }
        return fallback.get(route_name, 50.0)

# ─────────────────────────────────────────────────────────────
# BTI PREDICTION
# ─────────────────────────────────────────────────────────────
def predict_bti(lanes, length, avg_speed, std_dev, intersection, roadside_friction):
    bti = (0.3641
           + 0.0411  * lanes
           - 0.00308 * length
           - 0.01903 * avg_speed
           + 0.06103 * std_dev
           + 0.03981 * intersection
           + 0.00618 * roadside_friction)
    return round(max(0.1, min(bti, 2.0)), 4)

def estimate_buffer_time(bti, avg_tt):
    return round(bti * avg_tt, 1)

# ─────────────────────────────────────────────────────────────
# FUZZY AHP SCORING ENGINE
# Scores each route based on user characteristics weighted
# by Fuzzy AHP global weights
# ─────────────────────────────────────────────────────────────
def score_route_fahp(route, user_inputs, live_tt):
    """
    Score a route using Fuzzy AHP weights.
    Each variable is scored 0–1, then multiplied by its weight.
    Final score scaled to 0–100.
    """
    r   = route
    w   = FAHP_WEIGHTS
    bti = r["bti_predicted"]
    bt  = r["bt_predicted"]
    tt  = live_tt

    scores = {}

    # ── Commuter Type (w=0.1510) ────────────────────────────
    # Regular commuters prefer reliable routes (lower BTI)
    # Non-regular prefer familiar/simpler routes
    if user_inputs["commuter_type"] == "Regular":
        scores["commuter_type"] = (1 - min(bti, 1.5) / 1.5)
    else:
        scores["commuter_type"] = (1 - r["circularity"] / 2.0)

    # ── Buffer Kept (w=0.1691) ──────────────────────────────
    # Users who keep buffer → prefer routes with lower network BT demand
    if user_inputs["buffer_kept"] == "Yes":
        scores["buffer_kept"] = (1 - min(bt, 40) / 40)
    else:
        scores["buffer_kept"] = (1 - min(tt, 90) / 90)

    # ── Buffer Time (w=0.1056) ──────────────────────────────
    # Higher user buffer → less sensitive to route BT demand
    user_bt = user_inputs["buffer_time_min"]
    gap     = user_bt - bt
    # Positive gap = user over-buffers = safe, negative = under-buffer = risky
    scores["buffer_time"] = max(0, min(1, (gap + 20) / 40))

    # ── Travel Frequency (w=0.1001) ─────────────────────────
    # Daily commuters → familiar routes, value reliability
    freq_map = {"Daily": 1.0, "3–4 times/week": 0.8,
                "2–3 times/month": 0.5, "Once a month": 0.3,
                "1–2 times/month": 0.2}
    freq_w = freq_map.get(user_inputs["travel_freq"], 0.5)
    scores["travel_freq"] = freq_w * (1 - min(bti, 1.5)/1.5) + \
                            (1-freq_w) * (1 - r["circularity"]/2.0)

    # ── Route Following (w=0.0935) ──────────────────────────
    follow_map = {"Fully follow": 1.0, "Partially follow": 0.6,
                  "Does not follow": 0.2}
    follow_w = follow_map.get(user_inputs["route_following"], 0.5)
    # Strict followers prefer simpler (less circular) routes
    scores["route_following"] = follow_w * (1 - r["circularity"]/2.0) + \
                                (1-follow_w) * (1 - min(bti,1.5)/1.5)

    # ── Nav App (w=0.0667) ──────────────────────────────────
    if user_inputs["nav_app"] == "Yes":
        # App users → route doesn't matter much, app will guide
        scores["nav_app"] = 0.65
    else:
        # Non-app users prefer simpler, familiar routes
        scores["nav_app"] = (1 - r["circularity"]/2.0)

    # ── Trip Purpose (w=0.0660) ─────────────────────────────
    purpose_scores = {
        "Work":           (1 - min(tt,90)/90) * 0.7 + (1-min(bti,1.5)/1.5)*0.3,
        "Education":      (1 - min(bti,1.5)/1.5),
        "Medical":        (1 - min(tt,90)/90),
        "Social/Leisure": (1 - r["circularity"]/2.0),
    }
    scores["trip_purpose"] = purpose_scores.get(user_inputs["trip_purpose"], 0.5)

    # ── Corridor (w=0.0622) ─────────────────────────────────
    # Full corridor commuters care more about overall reliability
    if user_inputs["corridor"] == "Full corridor":
        scores["corridor"] = (1 - min(bti,1.5)/1.5)
    else:
        scores["corridor"] = (1 - min(tt,90)/90)

    # ── Delay Threshold (w=0.0393) ──────────────────────────
    thresh_map = {"1–2 min": 0.9, "2–5 min": 0.7,
                  "5–10 min": 0.4, "More than 10 min": 0.2}
    thresh_w = thresh_map.get(user_inputs["delay_threshold"], 0.5)
    scores["delay_threshold"] = thresh_w * (1 - min(bti,1.5)/1.5)

    # ── Occupation (w=0.0391) ───────────────────────────────
    occ_map = {
        "Working Professional": (1-min(tt,90)/90)*0.6 + (1-min(bti,1.5)/1.5)*0.4,
        "Cab / Commercial Driver": (1-min(tt,90)/90),
        "Student":              (1-min(bti,1.5)/1.5),
        "Self-employed":        (1-r["circularity"]/2.0),
        "Homemaker":            (1-r["circularity"]/2.0),
    }
    scores["occupation"] = occ_map.get(user_inputs["occupation"], 0.5)

    # ── Avg TT (w=0.0380) — now LIVE from TomTom ───────────
    scores["avg_tt"] = 1 - min(tt, 90) / 90

    # ── Time Bands (w=0.0239) ───────────────────────────────
    # More active time bands = more exposure = prefer reliable route
    bands = user_inputs["time_bands"]
    scores["time_bands"] = (bands/5) * (1-min(bti,1.5)/1.5)

    # ── When App (w=0.0234) ─────────────────────────────────
    when_map = {"Before trip": 0.6, "During trip": 0.7,
                "Both": 0.8, "Never": 0.3}
    scores["when_app"] = when_map.get(user_inputs["when_app"], 0.5)

    # ── Unreliable Segment (w=0.0220) ───────────────────────
    unrel_map = {"Junctions only": 0.4, "Road links only": 0.5, "Both": 0.3}
    # Match user's perception of unreliable segment vs route's unreliable type
    user_unrel = user_inputs["unreliable_seg"]
    route_unrel = r["unreliable"]
    if "Junction" in user_unrel and "Junction" in route_unrel:
        scores["unreliable_seg"] = 0.3   # user aware of this route's weakness
    elif "Road link" in user_unrel and "Road link" in route_unrel:
        scores["unreliable_seg"] = 0.3
    else:
        scores["unreliable_seg"] = 0.7   # mismatch = user not exposed to this issue

    # ── Weighted sum ────────────────────────────────────────
    total = sum(scores[k] * w[k] for k in scores)
    max_possible = sum(w.values())
    final_score = round(max(0, min(100, (total / max_possible) * 100)))

    return final_score, scores

# ─────────────────────────────────────────────────────────────
# FOLIUM MAP
# ─────────────────────────────────────────────────────────────
def build_map(routes_to_show, best_route_name=None):
    m = folium.Map(
        location=[28.585, 77.165],
        zoom_start=12,
        tiles="CartoDB positron"
    )

    for rname, coords in ROUTE_COORDS.items():
        if rname not in routes_to_show:
            continue
        color  = ROUTE_COLORS[rname]
        weight = 7 if rname == best_route_name else 3.5
        dash   = None if rname == best_route_name else "8 5"
        folium.PolyLine(
            coords, color=color, weight=weight,
            dash_array=dash, opacity=0.9,
            tooltip=rname
        ).add_to(m)

    # Origin marker
    folium.Marker(
        [28.6270, 77.2390],
        popup="Mandi House Circle (Origin)",
        tooltip="Origin: Mandi House",
        icon=folium.Icon(color="green", icon="play", prefix="fa")
    ).add_to(m)

    # Destination marker
    folium.Marker(
        [28.5290, 77.0940],
        popup="IFFCO Chowk (Destination)",
        tooltip="Destination: IFFCO Chowk",
        icon=folium.Icon(color="red", icon="stop", prefix="fa")
    ).add_to(m)

    # Route label markers
    folium.Marker(
        [28.5978, 77.1842],
        tooltip="Route 1: Sardar Patel Marg",
        icon=folium.DivIcon(html='<div style="font-size:11px;font-weight:bold;color:#1A73E8;background:white;padding:2px 5px;border-radius:4px;border:1px solid #1A73E8">SPM</div>')
    ).add_to(m)

    folium.Marker(
        [28.5688, 77.1572],
        tooltip="Route 2: Rao Tularam Marg",
        icon=folium.DivIcon(html='<div style="font-size:11px;font-weight:bold;color:#E8711A;background:white;padding:2px 5px;border-radius:4px;border:1px solid #E8711A">RTR</div>')
    ).add_to(m)

    return m

# ─────────────────────────────────────────────────────────────
# UI LAYOUT
# ─────────────────────────────────────────────────────────────
st.title("🛣️ Route Recommender")
st.caption("Mandi House → IFFCO Chowk · Real-time Travel Time · Fuzzy AHP Weighted Scoring")

col_form, col_map = st.columns([1, 1.6], gap="large")

with col_form:
    st.subheader("User characteristics")

    commuter_type  = st.selectbox("Commuter type",
                        ["Regular", "Non-regular"])
    trip_purpose   = st.selectbox("Trip purpose",
                        ["Work", "Education", "Medical", "Social/Leisure"])
    occupation     = st.selectbox("Occupation",
                        ["Working Professional", "Cab / Commercial Driver",
                         "Student", "Self-employed", "Homemaker"])
    travel_freq    = st.selectbox("Travel frequency",
                        ["Daily", "3–4 times/week", "2–3 times/month",
                         "Once a month", "1–2 times/month"])
    corridor       = st.selectbox("Corridor segment",
                        ["Full corridor", "Partial (joins midway)"])
    nav_app        = st.selectbox("Uses navigation app?",
                        ["Yes", "No"])
    when_app       = st.selectbox("When uses app",
                        ["Before trip", "During trip", "Both", "Never"],
                        disabled=(nav_app == "No"))
    route_following= st.selectbox("Route following behaviour",
                        ["Fully follow", "Partially follow", "Does not follow"])
    delay_threshold= st.selectbox("Delay threshold to switch route",
                        ["1–2 min", "2–5 min", "5–10 min", "More than 10 min"])
    buffer_kept    = st.selectbox("Do you keep buffer time?",
                        ["Yes", "No"])
    buffer_time_min= st.slider("Buffer time kept (min)", 0, 40, 15,
                        disabled=(buffer_kept == "No"))
    time_bands     = st.slider("Number of active travel time bands", 1, 5, 2)
    unreliable_seg = st.selectbox("Perceived unreliable segment",
                        ["Junctions only", "Road links only", "Both"])

    st.divider()
    st.subheader("Custom route")
    with st.expander("Add a custom route (BTI predicted)"):
        c_name  = st.text_input("Route name", "My Custom Route")
        c_lanes = st.slider("Avg lanes", 1, 6, 4)
        c_len   = st.number_input("Length (km)", 5.0, 40.0, 18.0, 0.5)
        c_speed = st.slider("Avg speed (km/h)", 10, 70, 28)
        c_std   = st.slider("Speed std dev (km/h)", 2, 20, 10)
        c_inter = st.slider("Intersection ratio", 0.0, 1.0, 0.5, 0.05)
        c_fric  = st.slider("Roadside friction ratio", 0.0, 1.0, 0.3, 0.05)
        c_circ  = st.slider("Circularity (1=straight, 2=very indirect)", 1.0, 2.0, 1.3, 0.05)
        c_merge = st.slider("Merge / diverge points", 0, 8, 3)
        c_unrel = st.selectbox("Unreliable segment type",
                               ["Junctions only", "Road links only", "Both"])
        add_custom = st.checkbox("Include in recommendation")

    run = st.button("🔍 Find best route", type="primary", use_container_width=True)

# ─────────────────────────────────────────────────────────────
# RESULTS
# ─────────────────────────────────────────────────────────────
with col_map:
    if not run:
        st.subheader("Route map")
        m = build_map(list(ROUTE_COORDS.keys()))
        st_folium(m, width=700, height=480)
        st.caption("Select your characteristics and click **Find best route**.")

    else:
        # Compile user inputs
        user_inputs = {
            "commuter_type":   commuter_type,
            "trip_purpose":    trip_purpose,
            "occupation":      occupation,
            "travel_freq":     travel_freq,
            "corridor":        corridor,
            "nav_app":         nav_app,
            "when_app":        when_app if nav_app == "Yes" else "Never",
            "route_following": route_following,
            "delay_threshold": delay_threshold,
            "buffer_kept":     buffer_kept,
            "buffer_time_min": buffer_time_min if buffer_kept == "Yes" else 0,
            "time_bands":      time_bands,
            "unreliable_seg":  unreliable_seg,
        }

        # Fetch live TT from TomTom
        with st.spinner("Fetching live travel times from TomTom..."):
            live_tt = {}
            for rname in NETWORK:
                live_tt[rname] = get_live_tt(rname)

        # Build route entries
        routes_scored = []
        for rname, rdata in NETWORK.items():
            tt   = live_tt[rname]
            bti  = predict_bti(rdata["avg_lanes"], rdata["total_length_km"],
                               rdata["avg_speed"], rdata["std_dev_speed"],
                               rdata["intersection_ratio"], rdata["roadside_friction"])
            bt   = estimate_buffer_time(bti, tt)
            entry = {
                **rdata,
                "name":          rname,
                "live_tt_min":   tt,
                "bti_predicted": bti,
                "bt_predicted":  bt,
            }
            score, breakdown = score_route_fahp(entry, user_inputs, tt)
            entry["score"]     = score
            entry["breakdown"] = breakdown
            routes_scored.append(entry)

        # Add custom route
        if add_custom:
            bti_c = predict_bti(c_lanes, c_len, c_speed, c_std, c_inter, c_fric)
            tt_c  = (c_len / c_speed) * 60 * c_circ   # estimated TT
            bt_c  = estimate_buffer_time(bti_c, tt_c)
            custom = {
                "name":              c_name,
                "avg_lanes":         c_lanes,
                "avg_speed":         c_speed,
                "std_dev_speed":     c_std,
                "signal_ratio":      0.5,
                "intersection_ratio":c_inter,
                "roadside_friction": c_fric,
                "merge_points":      c_merge,
                "circularity":       c_circ,
                "total_length_km":   c_len,
                "network_bt_min":    bt_c,
                "bti_measured":      bti_c,
                "bti_predicted":     bti_c,
                "bt_predicted":      bt_c,
                "live_tt_min":       tt_c,
                "unreliable":        c_unrel,
                "color":             "#6f42c1",
            }
            score_c, breakdown_c = score_route_fahp(custom, user_inputs, tt_c)
            custom["score"]     = score_c
            custom["breakdown"] = breakdown_c
            routes_scored.append(custom)

        routes_scored.sort(key=lambda x: x["score"], reverse=True)
        best = routes_scored[0]

        # MAP
        st.subheader("Route map")
        map_routes = [r["name"] for r in routes_scored if r["name"] in ROUTE_COORDS]
        m = build_map(map_routes, best["name"])
        st_folium(m, width=700, height=380)

        # RECOMMENDATION BANNER
        st.markdown(f"""
        <div style='background:#d4edda;border-radius:10px;
                    padding:14px 18px;margin-top:10px;margin-bottom:8px'>
          <div style='font-size:11px;font-weight:600;color:#155724;margin-bottom:4px'>
            ★ RECOMMENDED ROUTE
          </div>
          <div style='font-size:18px;font-weight:600;color:#155724'>
            {best["name"]}
          </div>
          <div style='font-size:13px;color:#1e7e34;margin-top:4px'>
            Score: {best["score"]}/100 &nbsp;|&nbsp;
            Live TT: {best["live_tt_min"]} min &nbsp;|&nbsp;
            Buffer demand: {best["bt_predicted"]} min &nbsp;|&nbsp;
            BTI: {best["bti_predicted"]}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # SCORE BAR CHART
        st.subheader("All routes — scored")
        fig = go.Figure()
        names_chart  = [r["name"].replace(" — ", "\n") for r in routes_scored]
        scores_chart = [r["score"] for r in routes_scored]
        colors_chart = [r.get("color","#888") for r in routes_scored]

        fig.add_trace(go.Bar(
            x=names_chart, y=scores_chart,
            marker_color=colors_chart,
            text=[f"{s}/100" for s in scores_chart],
            textposition="outside",
        ))
        fig.update_layout(
            yaxis=dict(range=[0,115], title="Recommendation score"),
            xaxis_title="Route",
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(size=12),
            margin=dict(t=20,b=60,l=40,r=20),
            height=290, showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        # LIVE TT DISPLAY
        st.subheader("Live travel times (TomTom)")
        tt_cols = st.columns(len(routes_scored))
        for i, r in enumerate(routes_scored):
            if r["name"] in ROUTE_COORDS:
                with tt_cols[i]:
                    st.metric(
                        label=r["name"].split("—")[0].strip(),
                        value=f"{r['live_tt_min']} min",
                        delta=f"BTI: {r['bti_predicted']}"
                    )

        # ROUTE DETAIL CARDS
        st.subheader("Route details")
        det_cols = st.columns(len(routes_scored))
        for i, r in enumerate(routes_scored):
            with det_cols[i]:
                border = "2px solid #28a745" if r["name"]==best["name"] \
                         else "0.5px solid #dee2e6"
                st.markdown(f"""
                <div style='border:{border};border-radius:10px;
                            padding:12px;margin-bottom:8px'>
                  <div style='font-size:13px;font-weight:600;
                              margin-bottom:8px;color:#333'>
                    {r["name"].split("—")[0].strip()}</div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    Score: <b>{r["score"]}/100</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    Live TT: <b>{r["live_tt_min"]} min</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    BTI (predicted): <b>{r["bti_predicted"]}</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    Buffer demand: <b>{r["bt_predicted"]} min</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    Length: <b>{r["total_length_km"]} km</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    Circularity: <b>{r["circularity"]}</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    Merge points: <b>{r["merge_points"]}</b></div>
                  <div style='font-size:11px;color:#666;margin:3px 0'>
                    Signals: <b>{round(r["signal_ratio"]*100)}%</b></div>
                  <div style='font-size:11px;color:#999;margin-top:6px'>
                    Unreliable: {r["unreliable"]}</div>
                </div>
                """, unsafe_allow_html=True)

        # WEIGHT BREAKDOWN
        with st.expander("📊 Fuzzy AHP weight breakdown for recommendation"):
            st.caption("Shows how each variable contributed to the score for the recommended route")
            bd = best["breakdown"]
            wt = FAHP_WEIGHTS
            breakdown_fig = go.Figure()
            var_labels = list(bd.keys())
            contributions = [bd[k]*wt[k]*100 for k in var_labels]
            breakdown_fig.add_trace(go.Bar(
                x=[k.replace("_"," ").title() for k in var_labels],
                y=contributions,
                marker_color="#1A73E8",
                text=[f"{c:.2f}" for c in contributions],
                textposition="outside",
            ))
            breakdown_fig.update_layout(
                yaxis_title="Weighted contribution (%)",
                xaxis_tickangle=-30,
                plot_bgcolor="white", paper_bgcolor="white",
                height=320, margin=dict(t=20,b=80,l=40,r=20),
            )
            st.plotly_chart(breakdown_fig, use_container_width=True)
