import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go
from datetime import datetime
import pytz

st.set_page_config(
    page_title="Route Recommender — Mandi House to IFFCO Chowk",
    layout="wide",
    page_icon="🛣️"
)
st.markdown("<style>.block-container{padding-top:1.5rem}</style>",
            unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
TOMTOM_KEY = "imAYgDRcFJmRBP4UKTdxWdgQp6LqZ9Rg"
ORIGIN     = "28.6270,77.2390"
DEST       = "28.5290,77.0940"

WAYPOINTS = {
    "Route 1 — Sardar Patel Marg (SPM)": "28.5912,77.1765",
    "Route 2 — Rao Tularam Marg (RTR)":  "28.5712,77.1542",
}
ROUTE_COLORS = {
    "Route 1 — Sardar Patel Marg (SPM)": "#1A73E8",
    "Route 2 — Rao Tularam Marg (RTR)":  "#E8711A",
}

# ─────────────────────────────────────────────────────────────
# NETWORK DATA
# ─────────────────────────────────────────────────────────────
BAND_NETWORK_BT = {
    "Route 1 — Sardar Patel Marg (SPM)": {
        "EMP":  5.90, "BMP": 12.06, "MP": 29.88,
        "IP":  18.73, "EP":  26.01, "EAP": 11.60,
    },
    "Route 2 — Rao Tularam Marg (RTR)": {
        "EMP":  5.69, "BMP": 11.52, "MP": 28.49,
        "IP":  17.65, "EP":  25.11, "EAP": 10.90,
    },
}
BAND_NETWORK_TT = {
    "Route 1 — Sardar Patel Marg (SPM)": {
        "EMP": 35.87, "BMP": 43.88, "MP": 63.13,
        "IP":  52.05, "EP":  58.24, "EAP": 45.44,
    },
    "Route 2 — Rao Tularam Marg (RTR)": {
        "EMP": 35.04, "BMP": 42.86, "MP": 61.41,
        "IP":  50.24, "EP":  57.57, "EAP": 43.32,
    },
}
MEASURED_BTI = {
    "Route 1 — Sardar Patel Marg (SPM)": 0.702,
    "Route 2 — Rao Tularam Marg (RTR)":  0.617,
}
BAND_BTI = {
    rname: {
        band: round(
            MEASURED_BTI[rname] *
            (BAND_NETWORK_BT[rname][band] / BAND_NETWORK_BT[rname]["EP"]),
            4
        )
        for band in ["EMP","BMP","MP","IP","EP","EAP"]
    }
    for rname in BAND_NETWORK_BT
}

def get_time_band():
    ist  = pytz.timezone("Asia/Kolkata")
    hour = datetime.now(ist).hour
    if   1  <= hour < 6:  return "EMP"
    elif 6  <= hour < 9:  return "BMP"
    elif 9  <= hour < 12: return "MP"
    elif 12 <= hour < 16: return "IP"
    elif 16 <= hour < 20: return "EP"
    else:                  return "EAP"

BAND_LABELS = {
    "EMP": "Early Morning (1–6)",
    "BMP": "Before Morning Peak (6–9)",
    "MP":  "Morning Peak (9–12)",
    "IP":  "Inter Peak (12–16)",
    "EP":  "Evening Peak (16–20)",
    "EAP": "Evening After Peak (20–24)",
}

NETWORK = {
    "Route 1 — Sardar Patel Marg (SPM)": {
        "avg_lanes": 3.9, "avg_speed": 26.6, "std_dev_speed": 10.8,
        "signal_ratio": 0.53, "intersection_ratio": 0.72,
        "roadside_friction": 0.34, "merge_points": 4,
        "circularity": 1.15, "total_length_km": 18.5,
        "unreliable": "Junctions and merging zones",
        "color": "#1A73E8",
        "name": "Route 1 — Sardar Patel Marg (SPM)",
        "_live_tt": 49.0,
    },
    "Route 2 — Rao Tularam Marg (RTR)": {
        "avg_lanes": 3.8, "avg_speed": 28.2, "std_dev_speed": 8.4,
        "signal_ratio": 0.44, "intersection_ratio": 0.78,
        "roadside_friction": 0.41, "merge_points": 3,
        "circularity": 1.45, "total_length_km": 20.1,
        "unreliable": "Road links and outer ring road merge",
        "color": "#E8711A",
        "name": "Route 2 — Rao Tularam Marg (RTR)",
        "_live_tt": 52.0,
    },
}

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
# TOMTOM
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_route(route_name):
    via = WAYPOINTS[route_name]
    url = (f"https://api.tomtom.com/routing/1/calculateRoute/"
           f"{ORIGIN}:{via}:{DEST}/json"
           f"?key={TOMTOM_KEY}&traffic=true&travelMode=car"
           f"&routeType=fastest&routeRepresentation=polyline")
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        route = data["routes"][0]
        tt_min = round(route["summary"]["travelTimeInSeconds"] / 60, 1)
        points = route["legs"][0]["points"] + route["legs"][1]["points"]
        coords = [[p["latitude"], p["longitude"]] for p in points]
        return tt_min, coords
    except Exception:
        fallback_coords = {
            "Route 1 — Sardar Patel Marg (SPM)": [
                [28.6270,77.2390],[28.6198,77.2165],[28.6045,77.1921],
                [28.5912,77.1765],[28.5788,77.1621],[28.5670,77.1430],
                [28.5480,77.1170],[28.5290,77.0940]],
            "Route 2 — Rao Tularam Marg (RTR)": [
                [28.6270,77.2390],[28.6198,77.2165],[28.6045,77.1921],
                [28.5712,77.1542],[28.5598,77.1388],
                [28.5420,77.1148],[28.5290,77.0940]],
        }
        fallback_tt = {
            "Route 1 — Sardar Patel Marg (SPM)": 49.0,
            "Route 2 — Rao Tularam Marg (RTR)":  52.0,
        }
        return fallback_tt[route_name], fallback_coords[route_name]

def get_dynamic_bt(route_name, live_tt, band):
    bt_base = BAND_NETWORK_BT[route_name][band]
    tt_base = BAND_NETWORK_TT[route_name][band]
    bti     = BAND_BTI[route_name][band]
    bt_live = round(bt_base * (live_tt / tt_base), 1)
    return bt_live, bti

# ─────────────────────────────────────────────────────────────
# SCORING ENGINE — TIME-BAND AWARE
#
# Key fix: band_rel_weight = mean BTI of current band
#   EMP (BTI~0.15) → rel_weight=0.30 → speed dominates → SPM likely wins
#   MP  (BTI~0.75) → rel_weight=0.82 → reliability dominates → RTR likely wins
#   EP  (BTI~0.65) → rel_weight=0.72 → reliability still important
#   EAP (BTI~0.29) → rel_weight=0.40 → balanced, SPM speed advantage helps
#
# This means the SAME user gets different recommendations at different times
# which is the correct real-world behaviour
# ─────────────────────────────────────────────────────────────
def score_route(route, user, tt, bt, bti, band):
    w     = WEIGHTS
    s     = {}
    circ  = route["circularity"]
    rname = route["name"]

    # ── Other route BTI for comparison ───────────────────────────────
    other_name = [k for k in NETWORK if k != rname][0]
    bti_other  = BAND_BTI[other_name][band]

    # ── rel_score: RTR=0.66, SPM=0.30 (consistent across bands) ─────
    max_bti   = max(bti, bti_other)
    rel_raw   = 1 - (bti / max_bti)           # SPM≈0.0, RTR≈0.12
    rel_score = max(0.25, min(0.75, 0.30 + rel_raw * 3.0))

    # ── spd_score: SPM=0.59, RTR=0.30 (based on live TT) ────────────
    tt_other  = NETWORK[other_name]["_live_tt"]
    max_tt    = max(tt, tt_other)
    spd_raw   = 1 - (tt / max_tt)             # SPM≈0.058, RTR≈0.0
    spd_score = max(0.25, min(0.75, 0.30 + spd_raw * 5.0))

    # ── dir_score: SPM=0.425, RTR=0.275 ──────────────────────────────
    dir_score = 1 - min(circ, 2.0) / 2.0

    # ── buf_score: lower demand = better ──────────────────────────────
    buf_score = 1 - min(bt, 40) / 40

    # ── TIME-BAND RELIABILITY WEIGHT ─────────────────────────────────
    # This is the key fix: at high-BTI bands (MP/EP) reliability matters
    # more for everyone; at low-BTI bands (EMP/EAP) speed matters more.
    # band_bti_mean = average absolute BTI level of current band
    band_bti_mean = (bti + bti_other) / 2
    # Scale: BTI=0.15 (EMP) → rel_weight=0.30, BTI=0.75 (MP) → rel_weight=0.82
    band_rel_weight = max(0.30, min(0.85, band_bti_mean * 1.10))
    band_spd_weight = 1.0 - band_rel_weight

    # ── Buffer Kept (w=0.284) ─────────────────────────────────────────
    if user["buffer_kept"] == "Yes":
        buf = user["buffer_time_min"]
        gap = buf - bt
        if gap >= 0:
            alpha = min(1.0, gap / 20.0)
            s["buffer_kept"] = alpha * rel_score + (1 - alpha) * buf_score
        else:
            s["buffer_kept"] = max(0.0, buf_score + gap / 40.0)
    else:
        s["buffer_kept"] = band_spd_weight * spd_score + band_rel_weight * buf_score

    # ── Commuter Type (w=0.253) ───────────────────────────────────────
    # At MP/EP: reliability critical for everyone → RTR
    # At EMP/EAP: speed/directness matter more → SPM
    if user["commuter_type"] == "Regular":
        s["commuter_type"] = band_rel_weight * rel_score + band_spd_weight * spd_score
    else:
        s["commuter_type"] = (band_rel_weight * 0.7) * rel_score + \
                             (band_spd_weight * 0.5) * dir_score + \
                             (band_spd_weight * 0.5) * spd_score

    # ── Buffer Time (w=0.177) ─────────────────────────────────────────
    gap2 = user["buffer_time_min"] - bt
    s["buffer_time"] = max(0.0, min(1.0, 0.5 + gap2 / 40.0))

    # ── Route Following (w=0.157) ─────────────────────────────────────
    follow_rel = {
        "Flexible — switches when needed": 0.85,
        "Partially follow":                0.50,
        "Habitual — stays on known route": 0.15,
    }
    fw = follow_rel.get(user["route_following"], 0.5)
    # At peak bands, even habitual users benefit from reliability
    fw_adj = min(0.95, fw + band_rel_weight * 0.15)
    s["route_following"] = fw_adj * rel_score + \
                           (1 - fw_adj) * (0.6 * spd_score + 0.4 * dir_score)

    # ── Trip Purpose (w=0.111) ────────────────────────────────────────
    # At peak bands: work trips care more about reliability
    # At off-peak: speed matters more for all purposes
    purpose_map = {
        "Work": (
            (0.35 + band_rel_weight * 0.2) * rel_score +
            (0.65 - band_rel_weight * 0.2) * spd_score
        ),
        "Education": (
            (0.20 + band_rel_weight * 0.3) * spd_score +
            (0.80 - band_rel_weight * 0.1) * rel_score
        ),
        "Medical": (
            (0.80 - band_rel_weight * 0.2) * spd_score +
            (0.20 + band_rel_weight * 0.2) * rel_score
        ),
        "Social/Leisure": (
            0.35 * spd_score + 0.25 * rel_score + 0.40 * dir_score
        ),
    }
    s["trip_purpose"] = purpose_map.get(user["trip_purpose"], 0.5)

    # ── Delay Threshold (w=0.066) ─────────────────────────────────────
    # At peak bands, low-threshold users care even more about reliability
    thresh_rel = {
        "1–2 min": 0.90, "2–5 min": 0.65,
        "5–10 min": 0.35, "More than 10 min": 0.10,
    }
    tr    = thresh_rel.get(user["delay_threshold"], 0.5)
    tr_adj = min(0.95, tr * (1 + band_rel_weight * 0.3))
    s["delay_threshold"] = tr_adj * rel_score + (1 - tr_adj) * spd_score

    # ── Occupation (w=0.066) ──────────────────────────────────────────
    # Cab drivers: speed always dominant regardless of band
    # Students: reliability dominant, amplified at peak
    occ_map = {
        "Working Professional": (
            (0.35 + band_rel_weight * 0.1) * rel_score +
            (0.65 - band_rel_weight * 0.1) * spd_score
        ),
        "Cab / Commercial Driver": (
            0.75 * spd_score + 0.25 * rel_score
        ),
        "Student": (
            (0.20) * spd_score +
            (0.80 + band_rel_weight * 0.05) * rel_score
        ),
        "Self-employed": (
            0.45 * spd_score + 0.30 * rel_score + 0.25 * dir_score
        ),
        "Homemaker": (
            0.30 * spd_score + 0.30 * rel_score + 0.40 * dir_score
        ),
    }
    s["occupation"] = occ_map.get(user["occupation"], 0.5)

    total = sum(s[k] * w[k] for k in s)
    score = round(max(0, min(100, (total / sum(w.values())) * 100)))
    return score, s

# ─────────────────────────────────────────────────────────────
# BUFFER GAP PANEL
# ─────────────────────────────────────────────────────────────
def show_buffer_gap_panel(routes_scored, user_buf, buffer_kept):
    st.subheader("🕐 Buffer Time: Kept vs Network Demand")
    if buffer_kept == "No":
        st.info("You chose not to keep buffer time. Network buffer demand shown for reference.")
        user_buf = 0

    cols = st.columns(len(routes_scored))
    for col, r in zip(cols, routes_scored):
        net_bt = r["bt"]
        gap    = round(user_buf - net_bt, 1)
        pct    = round((user_buf / net_bt * 100) if net_bt > 0 else 0)
        if gap >= 0:
            status = "✅ Sufficient buffer"
            sc = "#155724"; bg = "#d4edda"; gs = f"+{gap} min surplus"
        elif gap >= -5:
            status = "⚠️ Marginally under-buffered"
            sc = "#856404"; bg = "#fff3cd"; gs = f"{gap} min deficit"
        else:
            status = "❌ Under-buffered — delay risk"
            sc = "#721c24"; bg = "#f8d7da"; gs = f"{gap} min deficit"
        with col:
            st.markdown(f"""
            <div style='background:{bg};border-radius:10px;padding:14px 16px;margin-bottom:8px'>
              <b style='font-size:13px'>{r['name'].split('—')[0].strip()}</b><br>
              <small style='color:#555'>{'—'.join(r['name'].split('—')[1:]).strip()}</small>
              <hr style='margin:8px 0;border-color:#ccc'>
              <div style='font-size:12px;line-height:2.0'>
                You kept:&nbsp;<b>{user_buf} min</b><br>
                Network demands:&nbsp;<b>{net_bt} min</b>&nbsp;
                <small style='color:#888'>(BTI={r["bti"]:.4f})</small><br>
                Gap:&nbsp;<b style='color:{sc}'>{gs}</b><br>
                Coverage:&nbsp;<b>{pct}%</b> of demand met
              </div>
              <div style='margin-top:8px;font-size:12px;font-weight:700;color:{sc}'>{status}</div>
            </div>""", unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="User Buffer Kept",
        x=[r["name"].split("—")[0].strip() for r in routes_scored],
        y=[user_buf] * len(routes_scored),
        marker_color="#2196F3",
        text=[f"{user_buf} min"] * len(routes_scored),
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Network Buffer Demand",
        x=[r["name"].split("—")[0].strip() for r in routes_scored],
        y=[r["bt"] for r in routes_scored],
        marker_color=[r["color"] for r in routes_scored],
        text=[f"{r['bt']} min" for r in routes_scored],
        textposition="outside",
    ))
    fig.update_layout(
        barmode="group",
        yaxis=dict(
            range=[0, max(max(r["bt"] for r in routes_scored), user_buf) + 10],
            title="Buffer Time (min)"
        ),
        plot_bgcolor="white", paper_bgcolor="white",
        height=280, margin=dict(t=10, b=30, l=40, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────
# MAP
# ─────────────────────────────────────────────────────────────
def build_map(route_data, best_name=None):
    m = folium.Map(location=[28.585, 77.165], zoom_start=12,
                   tiles="CartoDB positron")
    for rname, (tt, coords) in route_data.items():
        color  = ROUTE_COLORS[rname]
        weight = 7 if rname == best_name else 3.5
        dash   = None if rname == best_name else "8 5"
        folium.PolyLine(coords, color=color, weight=weight,
                        dash_array=dash, opacity=0.9,
                        tooltip=f"{rname} — {tt} min").add_to(m)
    folium.Marker([28.6270, 77.2390], tooltip="Origin: Mandi House",
        icon=folium.Icon(color="green", icon="play", prefix="fa")).add_to(m)
    folium.Marker([28.5290, 77.0940], tooltip="Destination: IFFCO Chowk",
        icon=folium.Icon(color="red", icon="stop", prefix="fa")).add_to(m)
    return m

# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────
st.title("🛣️ Route Recommender")
st.caption("Mandi House → IFFCO Chowk  ·  Real-time TomTom Travel Time  ·  Fuzzy AHP Scoring")

current_band = get_time_band()
ist          = pytz.timezone("Asia/Kolkata")
current_time = datetime.now(ist).strftime("%I:%M %p")
st.info(f"🕐 Current IST time: **{current_time}** → Active band: **{BAND_LABELS[current_band]}** "
        f"— network BTI and buffer demand are set accordingly.")

for k in ["results", "route_data", "user_buf", "buf_kept"]:
    if k not in st.session_state:
        st.session_state[k] = None if k in ["results", "route_data"] \
                               else (15 if k == "user_buf" else "Yes")

col_form, col_map = st.columns([1, 1.6], gap="large")

with col_form:
    st.subheader("Your travel profile")
    commuter_type   = st.selectbox("Commuter type", ["Regular", "Non-regular"])
    trip_purpose    = st.selectbox("Trip purpose",
                        ["Work", "Education", "Medical", "Social/Leisure"])
    occupation      = st.selectbox("Occupation",
                        ["Working Professional", "Cab / Commercial Driver",
                         "Student", "Self-employed", "Homemaker"])
    delay_threshold = st.selectbox("How much delay before you switch route?",
                        ["1–2 min", "2–5 min", "5–10 min", "More than 10 min"])
    route_following = st.selectbox("Route switching behaviour",
                        ["Flexible — switches when needed",
                         "Partially follow", "Habitual — stays on known route"])
    buffer_kept     = st.selectbox("Do you keep buffer time before leaving?",
                        ["Yes", "No"])
    buffer_time_min = st.slider("How much buffer time? (min)", 0, 40, 15,
                        disabled=(buffer_kept == "No"))

    st.divider()
    st.markdown(f"**📊 Network BTI — {BAND_LABELS[current_band]}**")
    b1, b2 = st.columns(2)
    with b1:
        bti_spm = BAND_BTI["Route 1 — Sardar Patel Marg (SPM)"][current_band]
        bt_spm  = BAND_NETWORK_BT["Route 1 — Sardar Patel Marg (SPM)"][current_band]
        st.metric("SPM (Route 1)", f"BTI {bti_spm}", f"Net BT ~{bt_spm} min")
    with b2:
        bti_rtr = BAND_BTI["Route 2 — Rao Tularam Marg (RTR)"][current_band]
        bt_rtr  = BAND_NETWORK_BT["Route 2 — Rao Tularam Marg (RTR)"][current_band]
        st.metric("RTR (Route 2)", f"BTI {bti_rtr}", f"Net BT ~{bt_rtr} min")

    st.divider()
    run = st.button("🔍 Find best route", type="primary", use_container_width=True)

if st.session_state.route_data is None:
    with st.spinner("Loading live route data from TomTom..."):
        route_data = {}
        for rname in NETWORK:
            tt, coords = fetch_route(rname)
            route_data[rname] = (tt, coords)
        st.session_state.route_data = route_data
else:
    route_data = st.session_state.route_data

with col_map:
    st.subheader("Route map")

    if run:
        user = {
            "commuter_type":   commuter_type,
            "trip_purpose":    trip_purpose,
            "occupation":      occupation,
            "delay_threshold": delay_threshold,
            "route_following": route_following,
            "buffer_kept":     buffer_kept,
            "buffer_time_min": buffer_time_min if buffer_kept == "Yes" else 0,
        }

        for rname in NETWORK:
            live_tt_r, _ = route_data[rname]
            NETWORK[rname]["_live_tt"] = live_tt_r

        routes_scored = []
        for rname, rdata in NETWORK.items():
            live_tt, coords = route_data[rname]
            bt, bti = get_dynamic_bt(rname, live_tt, current_band)
            entry = {**rdata, "name": rname, "live_tt": live_tt,
                     "bti": bti, "bt": bt, "coords": coords}
            score, breakdown = score_route(entry, user, live_tt, bt, bti, current_band)
            entry.update({"score": score, "breakdown": breakdown})
            routes_scored.append(entry)

        routes_scored.sort(key=lambda x: x["score"], reverse=True)
        st.session_state.results  = routes_scored
        st.session_state.user_buf = buffer_time_min if buffer_kept == "Yes" else 0
        st.session_state.buf_kept = buffer_kept

    if st.session_state.results is None:
        st_folium(build_map(route_data), width=700, height=480)
        st.caption("Fill your travel profile and click **Find best route**.")
    else:
        routes_scored = st.session_state.results
        best = routes_scored[0]

        st_folium(build_map(route_data, best["name"]), width=700, height=320)

        st.markdown(f"""
        <div style='background:#d4edda;border-radius:10px;
                    padding:14px 18px;margin-top:8px;margin-bottom:6px'>
          <div style='font-size:11px;font-weight:600;color:#155724;margin-bottom:4px'>
            ★ RECOMMENDED ROUTE</div>
          <div style='font-size:18px;font-weight:700;color:#155724'>{best["name"]}</div>
          <div style='font-size:13px;color:#1e7e34;margin-top:4px'>
            Score: {best["score"]}/100 &nbsp;|&nbsp;
            Live TT: {best["live_tt"]} min &nbsp;|&nbsp;
            Network Buffer Demand: {best["bt"]} min &nbsp;|&nbsp;
            BTI ({BAND_LABELS[current_band]}): {best["bti"]:.4f}
          </div>
        </div>""", unsafe_allow_html=True)

        st.subheader("Route comparison")
        fig = go.Figure(go.Bar(
            x=[r["name"].replace(" — ", "\n") for r in routes_scored],
            y=[r["score"] for r in routes_scored],
            marker_color=[r["color"] for r in routes_scored],
            text=[f"{r['score']}/100" for r in routes_scored],
            textposition="outside",
        ))
        fig.update_layout(
            yaxis=dict(range=[0, 115], title="Recommendation score"),
            plot_bgcolor="white", paper_bgcolor="white",
            height=230, margin=dict(t=10, b=50, l=40, r=20),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        for col, r in zip([c1, c2], routes_scored):
            with col:
                st.metric(
                    label=r["name"].split("—")[0].strip(),
                    value=f"{r['live_tt']} min",
                    delta=f"BTI {r['bti']:.4f} · Buffer demand {r['bt']} min"
                )

        show_buffer_gap_panel(
            routes_scored,
            st.session_state.user_buf,
            st.session_state.buf_kept
        )

        with st.expander("📈 BTI across all time bands — both routes"):
            bands_order = ["EMP", "BMP", "MP", "IP", "EP", "EAP"]
            band_labels = ["EMP\n1-6", "BMP\n6-9", "MP\n9-12",
                           "IP\n12-16", "EP\n16-20", "EAP\n20-24"]
            fig3 = go.Figure()
            for rname, col in ROUTE_COLORS.items():
                fig3.add_trace(go.Scatter(
                    x=band_labels,
                    y=[BAND_BTI[rname][b] for b in bands_order],
                    mode="lines+markers",
                    name=rname.split("—")[0].strip(),
                    line=dict(color=col, width=2.5),
                    marker=dict(size=8),
                ))
            ci = bands_order.index(current_band)
            fig3.add_vline(x=ci, line_dash="dash", line_color="gray",
                           annotation_text=f"Now ({current_band})",
                           annotation_position="top")
            fig3.update_layout(
                yaxis_title="BTI", xaxis_title="Time Band",
                plot_bgcolor="white", paper_bgcolor="white",
                height=280, margin=dict(t=20, b=60, l=40, r=20),
                legend=dict(orientation="h", y=1.12),
            )
            st.plotly_chart(fig3, use_container_width=True)

            st.markdown("**Network Buffer Demand (min) by time band:**")
            import pandas as pd
            tbl = {
                "Band": band_labels,
                "SPM Net BT": [BAND_NETWORK_BT["Route 1 — Sardar Patel Marg (SPM)"][b]
                               for b in bands_order],
                "RTR Net BT": [BAND_NETWORK_BT["Route 2 — Rao Tularam Marg (RTR)"][b]
                               for b in bands_order],
            }
            st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

        st.subheader("Route details")
        det1, det2 = st.columns(2)
        for col, r in zip([det1, det2], routes_scored):
            with col:
                border = ("2px solid #28a745" if r["name"] == best["name"]
                          else "1px solid #dee2e6")
                st.markdown(f"""
                <div style='border:{border};border-radius:10px;padding:14px'>
                  <b>{r["name"].split("—")[0].strip()}</b><br>
                  <small style='color:#888'>
                    {'—'.join(r["name"].split("—")[1:]).strip()}
                  </small>
                  <hr style='margin:8px 0'>
                  <div style='font-size:12px;line-height:1.9'>
                  Score: <b>{r["score"]}/100</b><br>
                  Live travel time: <b>{r["live_tt"]} min</b><br>
                  BTI ({BAND_LABELS[current_band]}): <b>{r["bti"]:.4f}</b><br>
                  Network buffer demand: <b>{r["bt"]} min</b><br>
                  Length: <b>{r["total_length_km"]} km</b><br>
                  Avg speed: <b>{r["avg_speed"]} km/h</b><br>
                  Signals: <b>{round(r["signal_ratio"] * 100)}%</b><br>
                  Merge points: <b>{r["merge_points"]}</b><br>
                  Circularity: <b>{r["circularity"]}</b><br>
                  Unreliable segment: <i>{r["unreliable"]}</i>
                  </div>
                </div>""", unsafe_allow_html=True)

        with st.expander("📊 Fuzzy AHP score breakdown"):
            bd       = best["breakdown"]
            labels   = [k.replace("_", " ").title() for k in bd]
            contribs = [bd[k] * WEIGHTS[k] * 100 for k in bd]
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
                height=300, margin=dict(t=10, b=80, l=40, r=20),
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.caption("Weights source: Buckley Fuzzy AHP · 125 respondent survey data")
