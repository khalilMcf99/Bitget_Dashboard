import streamlit as st
import pandas as pd
import requests
import random
import arrow
from datetime import datetime

# ==========================================
# 1. 页面基础配置
# ==========================================
st.set_page_config(
    page_title="Bitget Token 看板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 高级 CSS 样式 (配合 config.toml 使用)
# ==========================================
st.markdown("""
<style>
    /* 调整顶部内边距，让页面更紧凑 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* 核心指标卡片样式 */
    .metric-card {
        background-color: #1B1E24;
        border: 1px solid #2B3139;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s;
        margin-bottom: 1rem;
    }

    .metric-card:hover {
        border-color: #0ECB81; /* 悬停时显示 Bitget 绿边框 */
        transform: translateY(-2px);
    }

    /* 字体颜色微调 */
    .metric-label { font-size: 0.9rem; color: #848E9C; }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #FFFFFF; }

    /* 涨跌幅颜色 */
    .trend-up { color: #0ECB81; font-weight: 600; }
    .trend-down { color: #F6465D; font-weight: 600; }

    /* 调整 DataFrame 样式，使其完全透明融入背景 */
    div[data-testid="stDataFrame"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

API_BASE_URL = "https://api.bitget.com"


# ==========================================
# 3. 数据服务层 (逻辑保持不变)
# ==========================================

@st.cache_data(ttl=10)
def get_all_tickers():
    try:
        url = f"{API_BASE_URL}/api/v2/spot/market/tickers"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data.get('code') != '00000': return pd.DataFrame()

        tickers = []
        for item in data['data']:
            last = float(item.get('lastPr', 0))
            open_24h = float(item.get('open', 0))
            change_24h = (last - open_24h) / open_24h if open_24h > 0 else 0

            # 模拟数据 (逻辑不变)
            random_factor = (hash(item['symbol']) % 100) / 1000
            change_1h = (change_24h / 6) + (random_factor * 0.05)
            change_4h = (change_24h / 2) + (random_factor * 0.1)

            tickers.append({
                "Symbol": item['symbol'].replace('USDT', ''),
                "Price": last,
                "Change 1h": change_1h,
                "Change 4h": change_4h,
                "Change 24h": change_24h,
                "High 24h": float(item.get('high24h', 0)),
                "Low 24h": float(item.get('low24h', 0)),
                "Volume (USDT)": float(item.get('usdtVolume', item.get('quoteVolume', 0))),
                "FullSymbol": item['symbol']
            })
        return pd.DataFrame(tickers)
    except Exception as e:
        return pd.DataFrame()


def get_coin_details(symbol):
    try:
        usdt_symbol = f"{symbol}USDT"
        ticker_res = requests.get(f"{API_BASE_URL}/api/v2/spot/market/tickers?symbol={usdt_symbol}").json()
        current_price = float(ticker_res['data'][0]['lastPr'])

        candle_url = f"{API_BASE_URL}/api/v2/spot/market/candles?symbol={usdt_symbol}&granularity=1h&limit=5"
        candles = requests.get(candle_url).json()['data']

        price_1h_ago = float(candles[1][4]) if len(candles) > 1 else current_price
        price_4h_ago = float(candles[4][4]) if len(candles) > 4 else current_price

        change_1h = (current_price - price_1h_ago) / price_1h_ago
        change_4h = (current_price - price_4h_ago) / price_4h_ago
        change_24h = float(ticker_res['data'][0]['open'])
        change_24h = (current_price - change_24h) / change_24h if change_24h > 0 else 0

        # 获取 OI
        oi_res = requests.get(
            f"{API_BASE_URL}/api/v2/mix/market/open-interest?symbol={usdt_symbol}&productType=USDT-FUTURES").json()
        oi_size = float(oi_res['data']['openInterestList'][0]['size']) if oi_res.get('data') and 'openInterestList' in \
                                                                          oi_res['data'] else 0
        oi_value = oi_size * current_price

        # 模拟 ATH/ATL
        seed = len(symbol)
        oi_ath = oi_value * (1.2 + (seed % 5) / 10)
        oi_atl = oi_value * (0.3 + (seed % 3) / 10)

        return {
            "symbol": symbol, "price": current_price,
            "change_1h": change_1h, "change_4h": change_4h, "change_24h": change_24h,
            "oi_value": oi_value, "oi_ath": oi_ath, "oi_atl": oi_atl
        }
    except:
        return None


# ==========================================
# 4. UI 渲染组件
# ==========================================

def format_currency(val):
    if val > 1_000_000_000:
        return f"${val / 1_000_000_000:.2f}B"
    elif val > 1_000_000:
        return f"${val / 1_000_000:.2f}M"
    else:
        return f"${val:,.0f}"


def render_html_card(data):
    if not data: return

    # 辅助颜色
    c_1h = "trend-up" if data['change_1h'] >= 0 else "trend-down"
    c_4h = "trend-up" if data['change_4h'] >= 0 else "trend-down"
    c_24h = "trend-up" if data['change_24h'] >= 0 else "trend-down"

    # 构建 HTML 卡片
    html_code = f"""
    <div class="metric-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <div style="font-size: 1.2rem; font-weight: bold; color: #EAECEF;">{data['symbol']} <span style="font-size: 0.8rem; color: #848E9C; background: #2B3139; padding: 2px 6px; border-radius: 4px;">PERP</span></div>
            <div class="metric-value">${data['price']:,.2f}</div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; margin-bottom: 15px;">
            <div><div class="metric-label">1H</div><div class="{c_1h}">{data['change_1h'] * 100:+.2f}%</div></div>
            <div><div class="metric-label">4H</div><div class="{c_4h}">{data['change_4h'] * 100:+.2f}%</div></div>
            <div style="text-align: right;"><div class="metric-label">24H</div><div class="{c_24h}">{data['change_24h'] * 100:+.2f}%</div></div>
        </div>

        <div style="border-top: 1px solid #2B3139; padding-top: 10px;">
            <div style="display: flex; justify-content: space-between;">
                <span class="metric-label">Open Interest</span>
                <span style="color: #EAECEF; font-weight: 500;">{format_currency(data['oi_value'])}</span>
            </div>
            <div style="margin-top: 5px; height: 6px; background: #2B3139; border-radius: 3px; overflow: hidden;">
                <div style="width: 70%; height: 100%; background: linear-gradient(90deg, #0ECB81 0%, #25a69a 100%);"></div>
            </div>
        </div>
    </div>
    """
    st.markdown(html_code, unsafe_allow_html=True)


# ==========================================
# 5. 主程序
# ==========================================

def main():
    col_title, col_btn = st.columns([6, 1])
    with col_title:
        st.title("Bitget Token 实时看板")
        st.caption(f"Last Updated: {datetime.now().strftime('%H:%M:%S')} (UTC)")
    with col_btn:
        # 这个按钮现在会自动应用 config.toml 里的 primaryColor (绿色)
        if st.button("🔄 刷新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # --- 第一部分：核心资产卡片 ---
    st.subheader("🔥 核心资产 & 持仓分析 (Open Interest)")
    majors = ["BTC", "ETH", "SOL"]
    cols = st.columns(3)
    for i, symbol in enumerate(majors):
        with cols[i]:
            detail_data = get_coin_details(symbol)
            render_html_card(detail_data)

    st.markdown("---")

    # --- 第二部分：所有代币表格 ---
    st.subheader("📊 现货行情概览")
    df = get_all_tickers()

    if not df.empty:
        col_search, _ = st.columns([1, 2])
        with col_search:
            search_term = st.text_input("🔍 搜索 Token", "", placeholder="BTC, ETH...").upper()

        if search_term:
            df = df[df['Symbol'].str.contains(search_term)]

        df = df.sort_values(by="Volume (USDT)", ascending=False).reset_index(drop=True)

        column_config = {
            "Symbol": st.column_config.TextColumn("Token", help="交易对名称"),
            "Price": st.column_config.NumberColumn("Price", format="$%.4f"),
            "Change 1h": st.column_config.NumberColumn("1h %", format="%.2f%%"),
            "Change 4h": st.column_config.NumberColumn("4h %", format="%.2f%%"),
            "Change 24h": st.column_config.NumberColumn("24h %", format="%.2f%%"),
            "High 24h": st.column_config.NumberColumn("High (24h)", format="$%.4f"),
            "Low 24h": st.column_config.NumberColumn("Low (24h)", format="$%.4f"),
            "Volume (USDT)": st.column_config.ProgressColumn(
                "Volume (24h)", format="$%f", min_value=0, max_value=df['Volume (USDT)'].max(),
            ),
            "FullSymbol": None
        }

        def color_change(val):
            return f'color: {"#0ECB81" if val >= 0 else "#F6465D"}'

        styled_df = df.style.applymap(color_change, subset=['Change 1h', 'Change 4h', 'Change 24h'])

        st.dataframe(
            styled_df,
            column_config=column_config,
            use_container_width=True,
            height=800,
            hide_index=True
        )
    else:
        st.error("无法加载市场数据，请检查网络连接。")


if __name__ == "__main__":
    main()