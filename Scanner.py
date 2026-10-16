import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader

# ---------------------- 初始化 ----------------------
st.set_page_config(page_title="烏賊戰術｜台股8策略選股器", layout="wide")
api = DataLoader()

# 若有 FinMind Token 請取消下方註解並填入
# api.login_by_token(api_token=st.secrets["FINMIND_TOKEN"])

# ---------------------- 策略定義（8套完整規則） ----------------------
strategy_list = {
    "策略一｜短期大波動+高週轉小型股": {
        "desc": """
✅ 條件：近20個交易日股價漲跌幅絕對值 >10%、近1日週轉率 >10%、股本 <20億元
❌ 過濾：股價<5元、五日均量<=500張剔除
""",
        "func": lambda df: (
            (abs(df["change_20d"]) > 0.10) &
            (df["turnover_rate"] > 10) &
            (df["capital"] < 20) &
            ~((df["close"] < 5) | (df["ma5_volume"] <= 500))
        )
    },
    "策略二｜30日橫盤+單日量能放大": {
        "desc": """
✅ 條件：近一日成交量 > 五日均量*1.2、近30個交易日股價漲跌幅絕對值 <1%
❌ 過濾：股價<5元、五日均量<=500張剔除
""",
        "func": lambda df: (
            (df["volume"] > df["ma5_volume"] * 1.2) &
            (abs(df["change_30d"]) < 0.01) &
            ~((df["close"] < 5) | (df["ma5_volume"] <= 500))
        )
    },
    "策略三｜10日波動+三倍爆量中小型股": {
        "desc": """
✅ 條件：近10個交易日股價漲跌幅絕對值 >1%、近一日成交量 >五日均量*3.0、近一日成交量 >100張、股本 <30億元
❌ 不過濾：保留股價5元以下、五日均量<=500張
""",
        "func": lambda df: (
            (abs(df["change_10d"]) > 0.01) &
            (df["volume"] > df["ma5_volume"] * 3.0) &
            (df["volume"] > 100) &
            (df["capital"] < 30)
        )
    },
    "策略四｜假突破轉弱，法人賣超": {
        "desc": """
✅ 條件：近一交易日股價 <5MA、近40個交易日股價漲跌幅絕對值 >30%、近10天三大法人累計賣超>10000張
❌ 過濾：股價<5元、五日均量<=500張剔除
""",
        "func": lambda df: (
            (df["close"] < df["ma5"]) &
            (abs(df["change_40d"]) > 0.30) &
            (df["institutional_10d_sell"] > 10000) &
            ~((df["close"] < 5) | (df["ma5_volume"] <= 500))
        )
    },
    "策略五｜營收創高基本面成長股 (效能優化版)": {
        "desc": """
✅ 條件：近一交易日股價 <50元、近三季EPS合計 >0.5元、近一年(12個月)營收創高、近一個月營收YoY >20%
❌ 不過濾：保留股價5元以下、五日均量<=500張
""",
        "func": lambda df: (
            (df["close"] < 50) &
            (df["eps_3q"] > 0.5) &
            (df["rev_12m_new_high"] == True) &
            (df["rev_growth_rate"] > 20)
        )
    },
    "策略六｜站上10MA+融券創10日新高": {
        "desc": """
✅ 條件：近一交易日股價 >10MA、近5個交易日股價漲跌幅絕對值 >10%、股本 <30億元、融券餘額創10日新高
❌ 不過濾：保留股價5元以下、五日均量<=500張
""",
        "func": lambda df: (
            (df["close"] > df["ma10"]) &
            (abs(df["change_5d"]) > 0.10) &
            (df["capital"] < 30) &
            (df["short_sell_10d_high"] == True)
        )
    },
    "策略七｜長期超跌+兩倍爆量反彈 (效能優化版)": {
        "desc": """
✅ 條件：近60個交易日股價漲跌幅 < -15%、近一日成交量 >五日均量*2.0、近一交易日股價 >5MA
❌ 不過濾：保留股價5元以下、五日均量<=500張
""",
        "func": lambda df: (
            (df["change_60d"] < -0.15) &
            (df["volume"] > df["ma5_volume"] * 2.0) &
            (df["close"] > df["ma5"])
        )
    },
    "策略八｜站上20MA窄盤+融券單日大增": {
        "desc": """
✅ 條件：近一交易日股價 <30元、近一交易日股價 >20MA、近3個交易日股價漲跌幅絕對值 <3%、股本 <50億元、近1日融券增 >8%
❌ 過濾：股價<5元、五日均量<=500張剔除
""",
        "func": lambda df: (
            (df["close"] < 30) &
            (df["close"] > df["ma20"]) &
            (abs(df["change_3d"]) < 0.03) &
            (df["capital"] < 50) &
            (df["short_sell_increase_rate"] > 8) &
            ~((df["close"] < 5) | (df["ma5_volume"] <= 500))
        )
    }
}

# ---------------------- 載入資料函數 ----------------------
@st.cache_data(ttl=3600, max_entries=500, show_spinner=False)
def load_tw_stock_data():
    import warnings
    warnings.filterwarnings("ignore")

    # 1. 每日股價資料 (縮減為90天，滿足最大60個交易日需求)
    df_daily = api.taiwan_stock_daily(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    )
    if df_daily.empty:
        raise ValueError("無法取得股價資料，可能觸發 API 限制。")
        
    df_daily = df_daily.sort_values(["stock_id", "date"])

    # 移動平均
    df_daily["ma5"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.rolling(5).mean())
    df_daily["ma10"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.rolling(10).mean())
    df_daily["ma20"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.rolling(20).mean())
    df_daily["ma5_volume"] = df_daily.groupby("stock_id")["volume"].transform(lambda x: x.rolling(5).mean())

    # 漲跌幅
    df_daily["change_3d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(3))
    df_daily["change_5d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(5))
    df_daily["change_10d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(10))
    df_daily["change_20d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(20))
    df_daily["change_30d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(30))
    df_daily["change_40d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(40))
    df_daily["change_60d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(60))

    if "turnover" in df_daily.columns:
        df_daily["turnover_rate"] = df_daily["turnover"]
    else:
        df_daily["turnover_rate"] = 0

    df_latest = df_daily.loc[df_daily.groupby("stock_id")["date"].idxmax()].copy()

    # 2. 股本資料
    df_info = api.taiwan_stock_info()
    df_info["capital"] = df_info["capital"] / 100_000_000
    df_merge = pd.merge(df_latest, df_info[["stock_id", "stock_name", "capital"]], on="stock_id", how="left")

    # 3. 三大法人 (縮減為20天，滿足10日累計)
    df_institutional = api.taiwan_stock_institutional_investors(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
    )
    if not df_institutional.empty:
        df_institutional["net_buy"] = (df_institutional.get("foreign_buy", 0) + 
                                       df_institutional.get("investment_buy", 0) + 
                                       df_institutional.get("dealer_buy", 0) - 
                                       df_institutional.get("foreign_sell", 0) - 
                                       df_institutional.get("investment_sell", 0) - 
                                       df_institutional.get("dealer_sell", 0))
        # 取近10個交易日累計
        df_inst_last10 = df_institutional.sort_values(["stock_id", "date"]).groupby("stock_id").tail(10)
        df_institutional_10d = df_inst_last10.groupby("stock_id")["net_buy"].sum().reset_index()
        df_institutional_10d.columns = ["stock_id", "institutional_10d_sell"]
        df_institutional_10d["institutional_10d_sell"] = -df_institutional_10d["institutional_10d_sell"]
        df_merge = pd.merge(df_merge, df_institutional_10d, on="stock_id", how="left")
    else:
        df_merge["institutional_10d_sell"] = 0

    # 4. 融券資料 (縮減為20天)
    df_short = api.taiwan_stock_short_sale(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
    )
    if not df_short.empty:
        df_short = df_short.sort_values(["stock_id", "date"])
        df_short["short_sell_10d_high"] = df_short.groupby("stock_id")["short_sale_balance"].transform(lambda x: x == x.rolling(window=10).max())
        df_short["short_sell_increase_rate"] = df_short.groupby("stock_id")["short_sale_balance"].transform(lambda x: x.pct_change() * 100)
        df_short_latest = df_short.loc[df_short.groupby("stock_id")["date"].idxmax()][["stock_id", "short_sell_10d_high", "short_sell_increase_rate"]]
        df_merge = pd.merge(df_merge, df_short_latest, on="stock_id", how="left")
    else:
        df_merge["short_sell_10d_high"] = False
        df_merge["short_sell_increase_rate"] = 0

    # 5. 營收 (抓400天計算近12個月新高)
    df_rev = api.taiwan_stock_month_revenue(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    )
    if not df_rev.empty:
        df_rev = df_rev.sort_values(["stock_id", "date"])
        df_rev["rev_12m_new_high"] = df_rev.groupby("stock_id")["revenue"].transform(lambda x: x == x.rolling(12, min_periods=1).max())
        df_rev["rev_growth_rate"] = df_rev.get("revenue_year_on_year", 0)
        df_rev_latest = df_rev.loc[df_rev.groupby("stock_id")["date"].idxmax()][["stock_id", "rev_12m_new_high", "rev_growth_rate"]]
        df_merge = pd.merge(df_merge, df_rev_latest, on="stock_id", how="left")
    else:
        df_merge["rev_12m_new_high"] = False
        df_merge["rev_growth_rate"] = 0

    # 6. EPS (400天算近三季)
    df_fin = api.taiwan_stock_financial_statement(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    )
    if not df_fin.empty:
        df_eps = df_fin[df_fin["type"].astype(str).str.contains("EPS", case=False, na=False)].copy() if "type" in df_fin.columns else pd.DataFrame()
        if df_eps.empty and "variable" in df_fin.columns:
            df_eps = df_fin[df_fin["variable"]=="EPS"].copy()
            
        if not df_eps.empty:
            df_eps = df_eps.sort_values(["stock_id", "date"])
            df_eps_3q = df_eps.groupby("stock_id")["value"].tail(3).groupby("stock_id").sum().reset_index()
            df_eps_3q.columns = ["stock_id", "eps_3q"]
            df_merge = pd.merge(df_merge, df_eps_3q, on="stock_id", how="left")
        else:
            df_merge["eps_3q"] = 0
    else:
        df_merge["eps_3q"] = 0

    df_merge = df_merge.fillna(0)
    return df_merge


# ---------------------- UI介面 ----------------------
st.title("🦑 烏賊戰術｜台股8套選股器")

# 側邊欄
st.sidebar.header("📊 選股設定")
selected_strategy_name = st.sidebar.selectbox("請選擇今日欲掃描的策略", list(strategy_list.keys()))
st.sidebar.markdown("---")
st.sidebar.info("💡 已啟動效能優化模式，減少資料抓取負擔。")

# 顯示選中的策略說明
st.subheader(f"目前選擇：{selected_strategy_name}")
st.markdown(strategy_list[selected_strategy_name]["desc"])

# 執行按鈕
if st.button("🚀 開始掃描符合條件的個股", type="primary"):
    with st.spinner("⏳ 正在拉取台股數據，並計算技術指標... (約需數十秒)"):
        try:
            df_all = load_tw_stock_data()
            strategy_filter = strategy_list[selected_strategy_name]["func"]
            df_result = df_all[strategy_filter(df_all)]
            
            display_columns = ["stock_id", "stock_name", "date", "close", "volume", "capital"]
            final_columns = [col for col in display_columns if col in df_result.columns]
            df_display = df_result[final_columns].reset_index(drop=True)
            
            if df_display.empty:
                st.warning("👀 今日無符合此策略條件的個股。")
            else:
                st.success(f"🎉 掃描完成！共篩選出 **{len(df_display)}** 檔符合條件的個股。")
                st.dataframe(df_display, use_container_width=True)
                
                csv_data = df_display.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="📥 匯出選股結果 (CSV格式)",
                    data=csv_data,
                    file_name=f"{selected_strategy_name}_選股結果.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"❌ 發生錯誤：{e}")
            st.info("⚠️ 可能是短時間內觸發了 API 限流，請稍後再試。")
