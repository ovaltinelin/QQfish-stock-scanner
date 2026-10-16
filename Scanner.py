import streamlit as st
import pandas as pd
import numpy as np
from FinMind.data import DataLoader

# ---------------------- 初始化 ----------------------
st.set_page_config(page_title="烏賊戰術｜台股8策略選股器", layout="wide")
api = DataLoader()

# 💡【強烈建議】如果您有申請 FinMind 的 API Token，請取消下面這行的註解並填寫
# api.login_by_token(api_token="請在此輸入您的_FinMind_API_Token")

# ---------------------- 策略定義（8套完整規則） ----------------------
strategy_list = {
    "策略一｜短期大波動+高週轉小型股": {
        "desc": """
✅ 條件：
1. 近20個交易日股價漲跌幅絕對值 >10%
2. 近1日週轉率 >10%
3. 股本 <20億元
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
✅ 條件：
1. 近一日成交量 > 五日均量*1.2
2. 近30個交易日股價漲跌幅絕對值 <1%
❌ 過濾：股價<5元、五日均量<=500張剔除
 人工參考：搭配外資投信動態判斷
""",
        "func": lambda df: (
            (df["volume"] > df["ma5_volume"] * 1.2) &
            (abs(df["change_30d"]) < 0.01) &
            ~((df["close"] < 5) | (df["ma5_volume"] <= 500))
        )
    },
    "策略三｜10日波動+三倍爆量中小型股": {
        "desc": """
✅ 條件：
1. 近10個交易日股價漲跌幅絕對值 >1%
2. 近一日成交量 >五日均量*3.0
3. 近一日成交量 >100張
4. 股本 <30億元
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
✅ 條件：
1. 近一交易日股價 <5MA
2. 近40個交易日股價漲跌幅絕對值 >30%
3. 近10天三大法人累計賣超>10000張
❌ 過濾：股價<5元、五日均量<=500張剔除
""",
        "func": lambda df: (
            (df["close"] < df["ma5"]) &
            (abs(df["change_40d"]) > 0.30) &
            (df["institutional_10d_sell"] > 10000) &
            ~((df["close"] < 5) | (df["ma5_volume"] <= 500))
        )
    },
    "策略五｜營收創高基本面成長股": {
        "desc": """
✅ 條件：
1. 近一交易日股價 <50元
2. 近三季EPS合計 >0.5元
3. 近一個月營收創歷史新高
4. 近一個月營收成長率 >20%
❌ 不過濾：保留股價5元以下、五日均量<=500張
""",
        "func": lambda df: (
            (df["close"] < 50) &
            (df["eps_3q"] > 0.5) &
            (df["rev_monthly_new_high"] == True) &
            (df["rev_growth_rate"] > 20)
        )
    },
    "策略六｜站上10MA+融券創10日新高": {
        "desc": """
✅ 條件：
1. 近一交易日股價 >10MA
2. 近5個交易日股價漲跌幅絕對值 >10%
3. 股本 <30億元
4. 融券餘額創10日新高
❌ 不過濾：保留股價5元以下、五日均量<=500張
""",
        "func": lambda df: (
            (df["close"] > df["ma10"]) &
            (abs(df["change_5d"]) > 0.10) &
            (df["capital"] < 30) &
            (df["short_sell_10d_high"] == True)
        )
    },
    "策略七｜長期超跌+兩倍爆量反彈": {
        "desc": """
✅ 條件：
1. 近120個交易日股價漲跌幅 < -20%
2. 近一日成交量 >五日均量*2.0
3. 近一交易日股價 >5MA
❌ 不過濾：保留股價5元以下、五日均量<=500張
""",
        "func": lambda df: (
            (df["change_120d"] < -0.20) &
            (df["volume"] > df["ma5_volume"] * 2.0) &
            (df["close"] > df["ma5"])
        )
    },
    "策略八｜站上20MA窄盤+融券單日大增": {
        "desc": """
✅ 條件：
1. 近一交易日股價 <30元
2. 近一交易日股價 >20MA
3. 近3個交易日股價漲跌幅絕對值 <3%
4. 股本 <50億元
5. 近1日融券餘額增加 >8%
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

# ---------------------- 載入資料函數，增加快取上限控制 ----------------------
@st.cache_data(ttl=3600, max_entries=500, show_spinner=False)
def load_tw_stock_data():
    import warnings
    warnings.filterwarnings("ignore")

    # 1. 每日股價資料 120天
    df_daily = api.taiwan_stock_daily(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=120)).strftime("%Y-%m-%d")
    )
    if df_daily.empty:
        raise ValueError("無法取得股價資料，可能觸發 API 限制。")
        
    df_daily = df_daily.sort_values(["stock_id", "date"])

    # 移動平均
    df_daily["ma5"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.rolling(5).mean())
    df_daily["ma10"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.rolling(10).mean())
    df_daily["ma20"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.rolling(20).mean())
    df_daily["ma5_volume"] = df_daily.groupby("stock_id")["volume"].transform(lambda x: x.rolling(5).mean())

    # 各區間漲跌幅
    df_daily["change_3d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(3))
    df_daily["change_5d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(5))
    df_daily["change_10d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(10))
    df_daily["change_20d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(20))
    df_daily["change_30d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(30))
    df_daily["change_40d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(40))
    df_daily["change_120d"] = df_daily.groupby("stock_id")["close"].transform(lambda x: x.pct_change(120))

    # 這裡原先您的 Turnover rate 寫法
    if "turnover" in df_daily.columns:
        df_daily["turnover_rate"] = df_daily["turnover"]
    else:
        df_daily["turnover_rate"] = 0 # 若無該欄位則防呆

    df_latest = df_daily.loc[df_daily.groupby("stock_id")["date"].idxmax()].copy()

    # 2. 股本資料
    df_info = api.taiwan_stock_info()
    df_info["capital"] = df_info["capital"] / 100_000_000
    df_merge = pd.merge(df_latest, df_info[["stock_id", "stock_name", "capital"]], on="stock_id", how="left")

    # 3. 三大法人 120天
    df_institutional = api.taiwan_stock_institutional_investors(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=120)).strftime("%Y-%m-%d")
    )
    if not df_institutional.empty:
        df_institutional["net_buy"] = (df_institutional.get("foreign_buy", 0) + 
                                       df_institutional.get("investment_buy", 0) + 
                                       df_institutional.get("dealer_buy", 0) - 
                                       df_institutional.get("foreign_sell", 0) - 
                                       df_institutional.get("investment_sell", 0) - 
                                       df_institutional.get("dealer_sell", 0))
        df_institutional_10d = df_institutional.groupby("stock_id")["net_buy"].sum().reset_index()
        df_institutional_10d.columns = ["stock_id", "institutional_10d_sell"]
        df_institutional_10d["institutional_10d_sell"] = -df_institutional_10d["institutional_10d_sell"]
        df_merge = pd.merge(df_merge, df_institutional_10d, on="stock_id", how="left")
    else:
        df_merge["institutional_10d_sell"] = 0

    # 4. 融券資料 120天
    df_short = api.taiwan_stock_short_sale(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=120)).strftime("%Y-%m-%d")
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

    # 5. 營收 (時間太長易被限制，縮短為 400 天確保可以算 YoY)
    df_rev = api.taiwan_stock_month_revenue(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    )
    if not df_rev.empty:
        df_rev = df_rev.sort_values(["stock_id", "date"])
        df_rev["rev_monthly_new_high"] = df_rev.groupby("stock_id")["revenue"].transform(lambda x: x == x.expanding().max())
        df_rev["rev_growth_rate"] = df_rev.get("revenue_year_on_year", 0)
        df_rev_latest = df_rev.loc[df_rev.groupby("stock_id")["date"].idxmax()][["stock_id", "rev_monthly_new_high", "rev_growth_rate"]]
        df_merge = pd.merge(df_merge, df_rev_latest, on="stock_id", how="left")
    else:
        df_merge["rev_monthly_new_high"] = False
        df_merge["rev_growth_rate"] = 0

    # 6. EPS (同理縮短天數)
    df_fin = api.taiwan_stock_financial_statement(
        start_date=(pd.Timestamp.now() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    )
    if not df_fin.empty:
        df_eps = df_fin[df_fin["type"].astype(str).str.contains("EPS", case=False, na=False)].copy() if "type" in df_fin.columns else pd.DataFrame()
        if df_eps.empty and "variable" in df_fin.columns: # FinMind 有時改版欄位名稱
            df_eps = df_fin[df_fin["variable"]=="EPS"].copy()
            
        if not df_eps.empty:
            df_eps = df_eps.