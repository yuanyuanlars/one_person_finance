# -*- coding: utf-8 -*-
"""
批量处理三个月测试账单：
1. 读取三个月测试账单.csv
2. 复用 tax_utils.auto_classify 对所有收支条目自动分类
3. 按月汇总收支，并调用 calculate_tax 计算月度税额
4. 生成收支汇总经营报表（Markdown + Excel），保存到项目目录
"""
import pandas as pd
from tax_utils import process_bill, calculate_tax

SRC_FILE = "三个月测试账单.csv"
DETAIL_CSV = "三个月账单_分类明细.csv"
REPORT_MD = "三个月经营报表.md"
REPORT_XLSX = "三个月经营报表.xlsx"

# ---------- 1. 读取并自动分类 ----------
df_raw = pd.read_csv(SRC_FILE)
df = process_bill(df_raw)  # 自动补列、分类、金额数值化

df["交易日期"] = pd.to_datetime(df["交易日期"], errors="coerce")
df["月份"] = df["交易日期"].dt.strftime("%Y-%m")
df = df.dropna(subset=["月份"]).sort_values("交易日期").reset_index(drop=True)

# 分类明细表（含月份）
detail_cols = ["月份", "交易日期", "交易描述", "交易金额", "大类", "明细分类"]
detail_df = df[detail_cols].copy()
detail_df["交易日期"] = detail_df["交易日期"].dt.strftime("%Y-%m-%d")
detail_df.to_csv(DETAIL_CSV, index=False, encoding="utf-8-sig")

# ---------- 2. 月度收支汇总 ----------
monthly_income = df[df["大类"] == "收入类"].groupby("月份")["交易金额"].sum()
monthly_cost = df[df["大类"] == "支出类"].groupby("月份")["交易金额"].sum()
months = sorted(df["月份"].unique())

summary_rows = []
tax_rows = []
for m in months:
    income = float(monthly_income.get(m, 0))
    cost = float(monthly_cost.get(m, 0))
    profit = income - cost
    tax = calculate_tax(income, cost)
    summary_rows.append({
        "月份": m,
        "营业收入": round(income, 2),
        "成本支出": round(cost, 2),
        "净利润": round(profit, 2),
        "毛利率(%)": round(profit / income * 100, 2) if income else 0,
    })
    tax_rows.append({
        "月份": m,
        **tax,
    })

summary_df = pd.DataFrame(summary_rows)
tax_df = pd.DataFrame(tax_rows)
total = summary_df[["营业收入", "成本支出", "净利润"]].sum()

# 明细分项统计（三个月合计）
cat_detail = (
    df.groupby(["大类", "明细分类"])["交易金额"]
    .agg(金额="sum", 笔数="count")
    .reset_index()
    .sort_values(["大类", "金额"], ascending=[True, False])
)
cat_detail["金额"] = cat_detail["金额"].round(2)

# ---------- 3. 生成 Excel 报表 ----------
with pd.ExcelWriter(REPORT_XLSX, engine="openpyxl") as writer:
    summary_df.to_excel(writer, sheet_name="月度收支汇总", index=False)
    tax_df.to_excel(writer, sheet_name="月度税额测算", index=False)
    cat_detail.to_excel(writer, sheet_name="分类统计", index=False)
    detail_df.to_excel(writer, sheet_name="分类明细", index=False)

# ---------- 4. 生成 Markdown 报表 ----------
md = []
md.append("# 一人财税 · 三个月经营报表（2026-09 ~ 2026-11）")
md.append("")
md.append("> 数据来源：三个月测试账单.csv，共 %d 笔交易，已自动分类。" % len(df))
md.append("")
md.append("## 一、总体概况")
md.append("")
md.append("| 指标 | 金额（元） |")
md.append("| --- | ---: |")
md.append(f"| 总营业收入 | {total['营业收入']:,.2f} |")
md.append(f"| 总成本支出 | {total['成本支出']:,.2f} |")
md.append(f"| 净利润 | {total['净利润']:,.2f} |")
md.append(f"| 净利率 | {total['净利润'] / total['营业收入'] * 100:.2f}% |")
md.append("")
md.append("## 二、月度收支汇总")
md.append("")
md.append(summary_df.to_markdown(index=False))
md.append("")
md.append("## 三、月度税额测算（小规模纳税人/个体工商户政策）")
md.append("")
md.append(tax_df.to_markdown(index=False))
md.append("")
md.append("## 四、收支分类统计（三个月合计）")
md.append("")
md.append(cat_detail.to_markdown(index=False))
md.append("")
md.append("## 五、计税说明")
md.append("")
md.append("- 增值税：月销售额不超过 10 万元免征；本期间各月收入均低于起征点，增值税为 0，附加税随之免征。")
md.append("- 个人经营所得税：按月利润×12 换算年度应纳税所得额，套用 5%~35% 超额累进级距计算年度税额后除以 12 得到月度估算值。")
md.append("- 明细账单见《三个月账单_分类明细.csv》，完整报表见《三个月经营报表.xlsx》。")
md.append("")

with open(REPORT_MD, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

# ---------- 5. 控制台输出摘要 ----------
print("=== 月度收支汇总 ===")
print(summary_df.to_string(index=False))
print("\n=== 月度税额 ===")
print(tax_df.to_string(index=False))
print("\n=== 合计 ===")
print(f"总收入 {total['营业收入']:,.2f} | 总支出 {total['成本支出']:,.2f} | 净利润 {total['净利润']:,.2f}")
print(f"\n已生成: {DETAIL_CSV} / {REPORT_MD} / {REPORT_XLSX}")
