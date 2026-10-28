import pandas as pd
from datetime import datetime

# ===================== 核心规则库（可扩展） =====================
# 收支分类关键词规则（可根据行业继续扩充）
CLASSIFY_RULES = {
    "收入类": {
        "主营业务收入": ["收款", "货款", "服务费", "设计费", "稿费", "营收", "订单", "咨询费"],
        "其他收入": ["退款", "返利", "补贴"]
    },
    "支出类": {
        "办公成本": ["办公", "文具", "打印", "软件", "会员", "域名", "服务器"],
        "差旅交通": ["打车", "高铁", "机票", "酒店", "差旅", "地铁", "公交"],
        "人力成本": ["工资", "劳务", "兼职", "外包"],
        "营销推广": ["广告", "推广", "流量", "投放", "佣金"],
        "进货成本": ["进货", "采购", "原材料", "货品"],
        "其他支出": ["餐饮", "招待", "水电", "房租"]
    }
}

# 税收政策参数（2026年小规模纳税人/个体工商户通用标准）
TAX_POLICY = {
    "增值税起征点": 100000,  # 月销售额10万免征
    "增值税征收率": 0.01,  # 小规模纳税人1%征收率
    "附加税税率": 0.06,  # 城建税+教育费附加等，按增值税额的6%（减半后）
    "经营所得税级距": [
        (30000, 0.05, 0),
        (90000, 0.10, 1500),
        (300000, 0.20, 10500),
        (500000, 0.30, 40500),
        (float("inf"), 0.35, 65500)
    ]
}

# ===================== 核心功能函数 =====================
def auto_classify(trade_desc):
    """根据交易描述自动分类收支"""
    trade_desc = str(trade_desc)
    # 先判断收入/支出大类
    for category, sub_dict in CLASSIFY_RULES.items():
        for sub_class, keywords in sub_dict.items():
            for kw in keywords:
                if kw in trade_desc:
                    return category, sub_class
    # 未匹配默认
    if any(x in trade_desc for x in ["收入", "收款", "转入"]):
        return "收入类", "其他收入"
    else:
        return "支出类", "其他支出"


def calculate_tax(month_income, month_cost):
    """计算月度税额：增值税+附加税+个人经营所得税（估算）"""
    policy = TAX_POLICY
    # 增值税计算
    if month_income <= policy["增值税起征点"]:
        vat = 0
    else:
        vat = month_income * policy["增值税征收率"]
    # 附加税
    surtax = vat * policy["附加税税率"]
    # 个人经营所得税（按年换算月度，应纳税所得额=收入-成本）
    annual_profit = (month_income - month_cost) * 12
    tax_payable = 0
    for limit, rate, quick_deduction in policy["经营所得税级距"]:
        if annual_profit <= limit:
            tax_payable = max(0, annual_profit * rate - quick_deduction)
            break
    monthly_income_tax = tax_payable / 12
    total_tax = vat + surtax + monthly_income_tax
    return {
        "增值税": round(vat, 2),
        "附加税": round(surtax, 2),
        "个人经营所得税(月估)": round(monthly_income_tax, 2),
        "月度总税额": round(total_tax, 2),
        "综合税负率": round(total_tax / month_income * 100, 2) if month_income > 0 else 0
    }


def process_bill(df):
    """处理上传的账单数据，自动分类"""
    # 兼容常见账单列名
    col_map = {}
    for col in df.columns:
        if "日期" in col or "时间" in col:
            col_map[col] = "交易日期"
        elif "描述" in col or "备注" in col or "摘要" in col:
            col_map[col] = "交易描述"
        elif "金额" in col:
            col_map[col] = "交易金额"
        elif "收支" in col or "类型" in col:
            col_map[col] = "收支类型"
    df = df.rename(columns=col_map)
    # 补全必要列
    if "交易日期" not in df.columns:
        df["交易日期"] = datetime.today().strftime("%Y-%m-%d")
    if "交易描述" not in df.columns:
        df["交易描述"] = "未备注交易"
    # 自动分类
    df[["大类", "明细分类"]] = df["交易描述"].apply(
        lambda x: pd.Series(auto_classify(x))
    )
    # 确保金额为数值
    df["交易金额"] = pd.to_numeric(df["交易金额"], errors="coerce").fillna(0)
    return df
