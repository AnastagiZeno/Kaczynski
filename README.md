# Kaczynski

个人的小工具游乐场，包含两个主要脚本：

## `big_a.py`
- 抓取国内宏观指标与六大指数，生成 PNG / CSV / HTML。
- 运行前请在虚拟环境里安装 `pandas numpy matplotlib plotly akshare`.
- 执行 `python big_a.py` 后会在仓库根目录输出 `china_10yr_macro_equity.{png,csv,html}`。

## `chelsea_schedule.py`
- 从 ESPN 赛程接口抓取切尔西上下各 30 天内的比赛，输出渐变风格的单页 HTML。
- 依赖 `requests`（与系统 `zoneinfo`）即可。
- 使用方式：
  ```bash
  python chelsea_schedule.py
  open chelsea_recent_fixtures.html  # Finder、xdg-open 或浏览器手动打开
  ```
