# big_a_v5.py —— 六大指数 × 宏观（15年；日/周/月），极简宽屏HTML版
import pandas as pd, numpy as np, datetime as dt
import matplotlib.pyplot as plt
import plotly.graph_objects as go, plotly.io as pio
import akshare as ak
import re

def _parse_zh_month_any(s: str) -> pd.Timestamp:
    """
    兼容 'YYYY年MM月份' / 'YYYY年MM月' / 'YYYY-MM' / 'YYYY/MM' 等格式，返回当月1日
    """
    if pd.isna(s):
        return pd.NaT
    s = str(s).strip()
    m = re.match(r"^(\d{4})[年/\-](\d{1,2})", s)
    if m:
        y, mth = int(m.group(1)), int(m.group(2))
        return pd.Timestamp(year=y, month=mth, day=1)
    try:
        return pd.to_datetime(s)
    except Exception:
        return pd.NaT

FREQ = "D"                      # "D"日 / "W-FRI"周五 / "ME"月末
BASE_DATE = "2014-01-01"        # 改这里：10年窗口
TITLE = f"中国10年宏观 × 六大指数（{FREQ} 频）"
OUT_PNG, OUT_CSV, OUT_HTML = "china_10yr_macro_equity.png", "china_10yr_macro_equity.csv", "china_10yr_macro_equity.html"
START_DATE, TODAY = "20140101", dt.date.today().strftime("%Y%m%d")
YESTERDAY = dt.date.today() - dt.timedelta(days=1)
END_DATE = YESTERDAY.strftime("%Y%m%d")           # 给 akshare 接口用
END_TS = pd.Timestamp(YESTERDAY)                  # 给 pandas 过滤用

# 最近5年的起点（用于Plotly初始窗口）
FIVE_YEARS_AGO = END_TS - pd.DateOffset(years=5)

plt.rcParams["font.sans-serif"] = ["PingFang SC","Arial Unicode MS","Microsoft YaHei","DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# ===== 指数映射：上证 / 新能源 / 芯片 / 半导体 / 高端装备制造 / 消费 =====
INDEX_MAP = {
    "上证综指": "sh000001",          # 上证
    "新能源": "sz399417",            # 中证新能源
    "芯片(980017.SZ)": "sz980017",   # 国证半导体芯片指数
    "半导体": "sz399812",           # 半导体（可替399801）
    "高端装备制造": "sz399396",      # 中证装备产业，近似高端制造
    "消费": "sh000932",              # 中证消费
}

# ===== 工具函数 =====
def _get_index_close_primary(symbol: str) -> pd.DataFrame:
    df = ak.stock_zh_index_daily(symbol=symbol)
    if "date" not in df.columns and "日期" in df.columns:
        df = df.rename(columns={"日期": "date", "收盘": "close"})
    elif "date" in df.columns:
        df = df.rename(columns={"date": "date", "close": "close"})
    else:
        raise ValueError("未找到日期字段")
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df["date"] >= pd.to_datetime(START_DATE)) & (df["date"] <= END_TS)]
    return df[["date","close"]].set_index("date").sort_index()

def _get_index_close_fallback(symbol_code: str) -> pd.DataFrame:
    code = symbol_code.replace("sz","").replace("sh","")
    df = ak.index_zh_a_hist(symbol=code, period="daily", start_date=START_DATE, end_date=END_DATE)
    if not {"日期","收盘"}.issubset(df.columns):
        raise ValueError("fallback结构变化")
    df = df.rename(columns={"日期":"date","收盘":"close"})
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] <= END_TS]
    return df[["date","close"]].set_index("date").sort_index()

def get_index_close(symbol: str) -> pd.DataFrame:
    try:
        if symbol.startswith(("sh","sz")) and symbol[-6:].isdigit():
            return _get_index_close_primary(symbol)
        return _get_index_close_fallback(symbol)
    except Exception:
        return _get_index_close_fallback(symbol)

def resample_index(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    return df if freq=="D" else df.resample(freq).last()

def parse_zh_month(s: str) -> pd.Timestamp:
    return pd.to_datetime(s, format="%Y年%m月份")

def upsample_macro_to(freq_index: pd.DatetimeIndex, monthly_df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    monthly = monthly_df.copy()
    monthly.index = monthly.index.to_period('M').to_timestamp('M')
    return monthly.reindex(freq_index, method="ffill")[[value_col]]

def load_m2_yoy_aligned(target_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    从 ak.macro_china_money_supply() 读取 M2 同比：
    - 模糊匹配“月份/时间”等日期列 & 任意包含“同比”的列（优先 M2 相关）
    - 将日期标准化为当月月末
    - 前向填充，上采样对齐到 target_index（日/周/月底）
    返回固定列名：'M2同比(%)'
    """
    try:
        t = ak.macro_china_money_supply()
        month_candidates = [c for c in t.columns if ("月" in c) or ("期" in c) or ("时间" in c)]
        if not month_candidates:
            raise ValueError("未找到月份列")
        month_col = month_candidates[0]

        yoy_col = next((c for c in t.columns if ("M2" in c and "同比" in c)), None)
        if yoy_col is None:
            yoy_candidates = [c for c in t.columns if "同比" in c]
            if not yoy_candidates:
                raise ValueError("未找到同比列")
            yoy_col = yoy_candidates[0]

        t["date"] = t[month_col].map(_parse_zh_month_any)
        df = (t[["date", yoy_col]]
              .rename(columns={yoy_col: "M2同比(%)"})
              .dropna(subset=["date"])
              .set_index("date")
              .sort_index())

        monthly = df.copy()
        monthly.index = monthly.index.to_period("M").to_timestamp("M")
        aligned = monthly.reindex(target_index, method="ffill")
        return aligned[["M2同比(%)"]]
    except Exception as e:
        print(f"[WARN] M2 加载失败：{e}")
        return pd.DataFrame()

# ===== 抓指数：原始点位 + 归一化 =====
series, raw_series = {}, {}
for name, sym in INDEX_MAP.items():
    try:
        raw = get_index_close(sym)
        raw = resample_index(raw, FREQ)
        raw = raw[(raw.index >= pd.to_datetime(BASE_DATE)) & (raw.index <= END_TS)]
        raw_series[name] = raw["close"]
        base = raw["close"].iloc[0]
        series[name] = raw["close"] / base * 100.0
        print(f"[OK] {name} {len(raw)}点（{FREQ}）")
    except Exception as e:
        print(f"[WARN] {name} 失败：{e}")

equity_df = pd.DataFrame(series)          # 归一化
equity_df_raw = pd.DataFrame(raw_series)  # 真实点位

# ===== 宏观：M2/CPI（上采样到同频） =====
def load_cpi_yoy_aligned(target_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    先试 macro_china_cpi（通常更稳，含'全国-同比'等列）
    再试 macro_china_cpi_monthly（含'当月同比'等）
    自动识别月份/同比列，按月末对齐到 target_index，并前向填充。
    返回列名固定为 'CPI同比(%)'
    """
    df = None

    try:
        t = ak.macro_china_cpi()
        month_col = next(c for c in t.columns if "月" in c)
        yoy_col = None
        for c in t.columns:
            if ("同比" in c) and ("全国" in c or c.endswith("同比")):
                yoy_col = c
                break
        if yoy_col is None:
            yoy_col = next(c for c in t.columns if "同比" in c)

        t["date"] = t[month_col].map(_parse_zh_month_any)
        df = (
            t[["date", yoy_col]]
            .rename(columns={yoy_col: "CPI同比(%)"})
            .dropna(subset=["date"])
            .set_index("date")
            .sort_index()
        )
    except Exception as e:
        print(f"[INFO] CPI首选源 macro_china_cpi 不可用：{e}")

    if df is None or df.empty:
        try:
            t = ak.macro_china_cpi_monthly()
            month_col = next(c for c in t.columns if "月" in c)
            yoy_col = next(c for c in t.columns if "同比" in c)
            t["date"] = t[month_col].map(_parse_zh_month_any)
            df = (
                t[["date", yoy_col]]
                .rename(columns={yoy_col: "CPI同比(%)"})
                .dropna(subset=["date"])
                .set_index("date")
                .sort_index()
            )
        except Exception as e:
            print(f"[WARN] CPI备用源 macro_china_cpi_monthly 也不可用：{e}")
            return pd.DataFrame()

    monthly = df.copy()
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    aligned = monthly.reindex(target_index, method="ffill")
    return aligned[["CPI同比(%)"]]

m2_yoy = cpi_yoy = None
try:
    m2_yoy = load_m2_yoy_aligned(equity_df.index)
    if not m2_yoy.empty:
        print(f"[OK] M2 同频：{len(m2_yoy)}")
    else:
        print("[WARN] M2 同频为空")
except Exception as e:
    print(f"[WARN] M2 失败：{e}")
    m2_yoy = pd.DataFrame()

try:
    cpi_yoy = load_cpi_yoy_aligned(equity_df.index)
    if not cpi_yoy.empty:
        print(f"[OK] CPI 同频：{len(cpi_yoy)}")
    else:
        print("[WARN] CPI 同频为空")
except Exception as e:
    print(f"[WARN] CPI 失败：{e}")
    cpi_yoy = pd.DataFrame()

df_all = equity_df.copy()
if m2_yoy is not None:
    df_all = df_all.join(m2_yoy, how="left")
if cpi_yoy is not None:
    df_all = df_all.join(cpi_yoy, how="left")
df_all.to_csv(OUT_CSV, encoding="utf-8-sig")
print(f"✅ CSV：{OUT_CSV}")

# ===== 静态 PNG（PPT备用）=====
plt.figure(figsize=(16, 8))
for cname in equity_df.columns:
    plt.plot(equity_df.index, equity_df[cname], label=cname, linewidth=1.2)
ax = plt.gca()
ax2 = ax.twinx()
if "M2同比(%)" in df_all.columns:
    ax2.plot(df_all.index, df_all["M2同比(%)"], linestyle="--", label="M2同比(%)")
if "CPI同比(%)" in df_all.columns:
    ax2.plot(df_all.index, df_all["CPI同比(%)"], linestyle=":", label="CPI同比(%)")
ax.set_title(TITLE, fontsize=16)
ax.set_ylabel("指数（归一化=100）")
ax2.set_ylabel("同比(%)")
lines, labels = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax2.legend(lines + lines2, labels + labels2, loc="upper left", fontsize=10)
ax.grid(alpha=.3)
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=200)
print(f"✅ PNG：{OUT_PNG}")

# ===== 交互 HTML（宽屏 + 无重叠）=====

# 默认点亮：新能源 / 芯片 / 消费
DEFAULT_ON = {
    "新能源",
    "芯片(980017.SZ)",
    "消费",
}

fig = go.Figure()
for cname in equity_df.columns:
    visible = True if cname in DEFAULT_ON else "legendonly"
    fig.add_trace(go.Scatter(
        x=equity_df.index,
        y=equity_df[cname],
        mode="lines",
        name=cname,
        hovertemplate="%{x|%Y-%m-%d}<br>" + cname + "：%{y:.2f}",
        line=dict(width=1.3),
        connectgaps=True,
        visible=visible,
    ))

if "M2同比(%)" in df_all.columns:
    fig.add_trace(go.Scatter(
        x=df_all.index, y=df_all["M2同比(%)"], name="M2同比(%)",
        mode="lines", line=dict(dash="dash", width=1.5), yaxis="y2",
        hovertemplate="%{x|%Y-%m-%d}<br>M2同比：%{y:.2f}%",
        visible="legendonly"
    ))
if "CPI同比(%)" in df_all.columns:
    fig.add_trace(go.Scatter(
        x=df_all.index, y=df_all["CPI同比(%)"], name="CPI同比(%)",
        mode="lines", line=dict(dash="dot", width=1.5), yaxis="y2",
        hovertemplate="%{x|%Y-%m-%d}<br>CPI同比：%{y:.2f}%",
        visible="legendonly"
    ))

fig.update_layout(
    template="plotly_white",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=13, family="PingFang SC, Arial"),
    hoverlabel=dict(bgcolor="white", font_size=12, font_color="black"),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.12, xanchor="right", x=1),
    xaxis=dict(
        title=None,
        # 初始显示最近5年
        range=[FIVE_YEARS_AGO, END_TS],
        rangeselector=dict(
            buttons=[
                dict(count=6, label="6月", step="month", stepmode="backward"),
                dict(count=1, label="1年", step="year", stepmode="backward"),
                dict(count=3, label="3年", step="year", stepmode="backward"),
                dict(count=5, label="5年", step="year", stepmode="backward"),
                dict(step="all", label="10年"),
            ],
            x=0, xanchor="left", y=1.12, yanchor="bottom",
            bgcolor="rgba(255,255,255,0.6)",
            activecolor="rgba(27,115,232,0.2)",
            font=dict(size=12),
        ),
        rangeslider=dict(visible=False),
        # 中文刻度：2025年07月
        tickformat="%Y年%m月",
    ),
    yaxis=dict(visible=False),
    yaxis2=dict(visible=False),
    margin=dict(l=60, r=60, t=120, b=60),
)

CSS = """
<style>
:root{--bg:#0b0d10;--card:#111418;--muted:#9aa4b2;--text:#e8eef6;--grid:#222831;}
html.light{--bg:#fff;--card:#f7f8fa;--muted:#667085;--text:#101828;--grid:#e5e7eb;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei','Helvetica Neue',Arial,'Noto Sans SC',sans-serif;}
.container{max-width:1680px; margin:28px auto; padding:0 20px;}
.header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:12px}
h1{font-size:22px;margin:0} .desc{color:var(--muted);margin:6px 0 0;font-size:13px}
.links{font-size:13px;color:var(--muted)} .links a{color:#69b1ff;text-decoration:none;margin-left:14px}
.card{background:var(--card);border:1px solid var(--grid);border-radius:14px;padding:14px 14px 8px}
.tablewrap{margin-top:12px;overflow:auto;border:1px solid var(--grid);border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:13px;min-width:520px}
th,td{padding:10px 12px;border-bottom:1px solid var(--grid);white-space:nowrap}
th{text-align:left;color:var(--muted);background:rgba(0,0,0,0.04)}
.footer{color:var(--muted);font-size:12px;margin-top:12px;line-height:1.6}
@media (max-width: 960px){
  .container{padding:0 12px; max-width: 100%}
  h1{font-size:18px}
}
</style>
"""

latest_date = equity_df_raw.dropna(how="all").index[-1]
latest_raw  = equity_df_raw.loc[latest_date]
macro_cols  = [c for c in ["M2同比(%)","CPI同比(%)"] if c in df_all.columns]
latest_macro = df_all[macro_cols].iloc[-1] if macro_cols else pd.Series(dtype=float)

snap = pd.concat([latest_raw, latest_macro])

order = list(equity_df_raw.columns) + macro_cols
snap = snap.reindex(order)

def fmt_val(name, v):
    if pd.isnull(v):
        return ""
    is_equity = name in equity_df_raw.columns
    if is_equity:
        return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.2f}"
    else:
        return f"{v:.2f}%"

rows_html = "".join(f"<tr><td>{k}</td><td>{fmt_val(k, v)}</td></tr>" for k, v in snap.items())
TABLE_HTML = f"""
<div class='tablewrap'>
  <table>
    <thead><tr><th>系列</th><th>最新值</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
"""
AS_OF_TXT = f"（数据截止：{END_TS.date()}）"
INTRO = f"""
<div class="container">
  <div class="header">
    <div>
      <h1>{TITLE}</h1>
      <p class="desc">左轴：六大股指（基期=2014-01=100）；右轴：M2/CPI 同比（%）。图例可点击开关各曲线；支持框选放大、双击重置。{AS_OF_TXT}</p>
    </div>
    <div class="links" style="margin-left:auto;">
      <a href='html/{OUT_CSV}' download>CSV</a>
      <a href='html/{OUT_PNG}' download>PNG</a>
    </div>
  </div>
  <div class="card"><!-- PLOTLY_CHART --></div>
  <h3 style="margin:14px 0 8px;font-size:15px;">数据快照（真实点位）</h3>
  {TABLE_HTML}
  <div class="footer">
    频率：<b>{FREQ}</b>；股指曲线为归一化展示（便于对比），上表显示真实指数点位；宏观为同比（%），已上采样并前向填充对齐到所选频率。
  </div>
</div>
"""

plot_html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False, config={"displaylogo": False})
HTML = f"""<!doctype html>
<html lang="zh-CN" class="light">
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
{CSS}
<body>{INTRO.replace("<!-- PLOTLY_CHART -->", plot_html)}
</body></html>"""

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(HTML)
print(f"✅ HTML：{OUT_HTML}")
print("完成")
