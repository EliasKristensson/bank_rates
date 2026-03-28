import yfinance as yf
from io import StringIO
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
    tables = pd.read_html(StringIO(html))

    # Find the correct table (the one with many rows)
    df = max(tables, key=lambda x: len(x))

    # Rename columns (adjust if needed)
    df.columns = ["Date", "5y", "4y", "3y", "2y", "1y", "3m"]

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


@st.cache_data
def fetch_fund_data():
    tickers = {
        "Bas 75 A": ["0P00009H3K.ST", "0P00009H3K"],
        "Bas 100 A": ["0P00013YB6.ST", "0P00013YB6"],
    }

    all_data = []

    for name, ticker_list in tickers.items():
        df = pd.DataFrame()

        for ticker_symbol in ticker_list:
            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(period="max")

            if not df.empty:
                break

        if not df.empty:
            df = df.reset_index()
            df["Date"] = df["Date"].dt.tz_localize(None)
            df = df.rename(columns={"Close": "Price"})
            df["Fund"] = name
            all_data.append(df)

    if all_data:
        return pd.concat(all_data)

    return pd.DataFrame()

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
rate_columns = ["3m", "1y", "2y", "3y", "4y", "5y"]
selected_rates = st.sidebar.multiselect(
    "Select interest rates",
    rate_columns,
    default=list(rate_columns[:3]),
)

selected_funds = st.sidebar.multiselect(
    "Select funds",
    ["Bas 75 A", "Bas 100 A"],
    default=["Bas 75 A", "Bas 100 A"],
)

fund_df = fetch_fund_data()

fund_filtered = fund_df[
    (fund_df["Date"] >= pd.to_datetime(date_range[0])) &
    (fund_df["Date"] <= pd.to_datetime(date_range[1])) &
    (fund_df["Fund"].isin(selected_funds))
]

st.subheader("📊 Swedbank Robur Funds")

if fund_filtered.empty:
    st.warning("⚠️ Could not fetch fund data automatically.")

else:
    fig2 = px.line(
        fund_filtered,
        x="Date",
        y="Price",
        color="Fund",  # 🔥 KEY: separates the two lines
    )

    fig2.update_traces(line=dict(width=3))

    fig2.update_layout(
        template="plotly_white",
        title={
            "text": "Fund Value Over Time",
            "x": 0.02,
            "xanchor": "left",
            "font": dict(size=22)
        },
        xaxis=dict(showgrid=False),
        yaxis=dict(
            title="Price",
            gridcolor="rgba(0,0,0,0.05)"
        ),
        legend=dict(
            orientation="h",
            y=1.08,
            x=0,
            xanchor="left",
            bgcolor="rgba(255,255,255,0.6)"
        ),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40),
    )

    st.plotly_chart(fig2, width="stretch")

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
            orientation="h",
            y=1.08,
            x=0,
            xanchor="left",
            bgcolor="rgba(255,255,255,0.6)"
        ),

        hovermode="x unified",

        margin=dict(l=40, r=40, t=60, b=40),
    )

    fig.update_yaxes(ticksuffix="%")

    fig.update_traces(
        hovertemplate="%{y:.2f}%<extra>%{fullData.name}</extra>"
    )

    st.plotly_chart(fig, width="stretch")

else:
    st.warning("Select at least one rate type.")

# -------------------------
# DATA TABLE
# -------------------------
with st.expander("Show raw data"):
    st.dataframe(df_filtered)
