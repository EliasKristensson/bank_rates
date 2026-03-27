import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px

URL = "https://www.sparbankenskane.se/privat/rantor-priser-och-kurser/bolanerantor/historik-bolanerantor.html"

st.set_page_config(layout="wide")
st.title("📈 Mortgage Interest Rates (Sparbanken Skåne)")

# -------------------------
# DATA FETCH FUNCTION
# -------------------------
@st.cache_data
def fetch_data():
    import requests
    import pandas as pd

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(URL, headers=headers)
    html = response.text

    # Read ALL tables
    tables = pd.read_html(html)

    # Find the correct table (the one with many rows)
    df = max(tables, key=lambda x: len(x))

    # Rename columns (adjust if needed)
    df.columns = ["Date", "3m", "1y", "2y", "3y", "4y", "5y"]

    # Clean date column
    df["Date"] = (
        df["Date"]
        .astype(str)
        .str.replace(",", "-", regex=False)
    )
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Clean numeric columns
    for col in df.columns[1:]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", ".", regex=False)   # Swedish → standard decimal
            .str.replace("%", "", regex=False)    # remove % if present
            .str.replace(r"[^\d\.]", "", regex=True)
            .str.replace(r"\.+", ".", regex=True)
        )

        df[col] = pd.to_numeric(df[col], errors="coerce")

        # 🔥 KEY FIX: ensure everything is treated as percent (not fraction)
        # If values look like 434 instead of 4.34 → fix scale
        df[col] = df[col].apply(lambda x: x / 100 if x > 20 else x)

    # Drop bad rows
    df = df.dropna(subset=["Date"])

    return df.sort_values("Date")


# -------------------------
# REFRESH BUTTON
# -------------------------
if st.button("🔄 Refresh data"):
    fetch_data.clear()

df = fetch_data()

# -------------------------
# SIDEBAR CONTROLS
# -------------------------
st.sidebar.header("Controls")

# Time range
min_date = df["Date"].min().to_pydatetime()
max_date = df["Date"].max().to_pydatetime()

date_range = st.sidebar.slider(
    "Select time range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="YYYY-MM-DD"
)

# Filter by date
mask = (df["Date"] >= date_range[0]) & (df["Date"] <= date_range[1])
df_filtered = df.loc[mask]

# Select rate types
rate_columns = df.columns[1:]
selected_rates = st.sidebar.multiselect(
    "Select interest rates",
    rate_columns,
    default=list(rate_columns[:3]),
)

# -------------------------
# PLOT
# -------------------------
if selected_rates:
    df_melt = df_filtered.melt(
        id_vars="Date",
        value_vars=selected_rates,
        var_name="Rate Type",
        value_name="Interest Rate (%)",
    )

    fig = px.line(
        df_melt,
        x="Date",
        y="Interest Rate (%)",
        color="Rate Type",
    )

    # 🎨 STYLE UPGRADE
    fig.update_traces(
        mode="lines",
        line=dict(width=3),
    )

    fig.update_layout(
        template="plotly_white",

        title={
            "text": "Mortgage Interest Rates",
            "x": 0.02,
            "xanchor": "left",
            "font": dict(size=22)
        },

        xaxis=dict(
            title="",
            showgrid=False,
            zeroline=False
        ),

        yaxis=dict(
            title="Interest rate (%)",
            gridcolor="rgba(0,0,0,0.05)",
            zeroline=False
        ),

        legend=dict(
            title="",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),

        hovermode="x unified",

        margin=dict(l=40, r=40, t=60, b=40),
    )

    fig.update_yaxes(ticksuffix="%")

    fig.update_traces(
        hovertemplate="%{y:.2f}%<extra>%{fullData.name}</extra>"
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Select at least one rate type.")
    
# -------------------------
# DATA TABLE
# -------------------------
with st.expander("Show raw data"):
    st.dataframe(df_filtered)