from mcp.server.fastmcp import FastMCP
import pandas as pd
from datetime import datetime
from tax_utils import auto_classify, calculate_tax, process_bill

# 创建MCP服务
mcp = FastMCP("一人财税工具")

# 技能1：账单自动分类
@mcp.tool()
def bill_classify(trade_desc: str) -> dict:
    """
    根据交易描述自动判断收支大类和明细分类
    参数：trade_desc 交易描述/摘要
    """
    category, sub_class = auto_classify(trade_desc)
    return {
        "交易描述": trade_desc,
        "大类": category,
        "明细分类": sub_class
    }

# 技能2：税额精准测算
@mcp.tool()
def tax_calculate(month_income: float, month_cost: float) -> dict:
    """
    计算月度增值税、附加税、个人经营所得税及综合税负
    参数：month_income 月营业收入(元)，month_cost 月成本支出(元)
    """
    return calculate_tax(month_income, month_cost)

# 技能3：生成经营报表
@mcp.tool()
def report_generate(csv_file: str = "三个月测试账单.csv") -> dict:
    """
    读取账单CSV文件，自动分类并生成收支汇总报表
    参数：csv_file 账单文件路径，默认三个月测试账单.csv
    """
    try:
        df = pd.read_csv(csv_file)
        df_processed = process_bill(df)
        income_total = df_processed[df_processed["大类"] == "收入类"]["交易金额"].sum()
        cost_total = df_processed[df_processed["大类"] == "支出类"]["交易金额"].sum()
        profit = income_total - cost_total

        # 保存报表到本地
        report_name = f"经营报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_processed.to_csv(report_name, index=False, encoding="utf-8-sig")

        return {
            "状态": "生成成功",
            "总收入": round(income_total, 2),
            "总支出": round(cost_total, 2),
            "净利润": round(profit, 2),
            "报表文件": report_name
        }
    except Exception as e:
        return {"状态": "失败", "原因": str(e)}

if __name__ == "__main__":
    mcp.run()
