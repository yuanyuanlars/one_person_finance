import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from tax_policy_crawler import TaxPolicyCrawler
import json
import os


# ===================== 页面基础配置 =====================
st.set_page_config(
    page_title="一人财税 - OPC创业者轻量化财税工具",
    page_icon="💰",
    layout="wide"
)
# 初始化当前页面
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "首页介绍"

# ===================== 加载外部CSS美化样式 =====================
def load_css(css_file):
    with open(css_file, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# 调用加载
load_css("style.css")

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
# ===================== 账单本地持久化工具 =====================
BILL_FILE = "user_bill_data.csv"

def save_bill_to_local(df):
    """将账单数据保存到本地CSV文件"""
    df.to_csv(BILL_FILE, index=False, encoding="utf-8-sig")

def load_bill_from_local():
    """从本地加载账单数据，不存在则返回空"""
    import os
    if os.path.exists(BILL_FILE):
        df = pd.read_csv(BILL_FILE)
        return df
    return pd.DataFrame()

# 页面启动时，自动把本地数据加载到会话中
if "user_bill_data" not in st.session_state:
    st.session_state["user_bill_data"] = load_bill_from_local()


# ===================== 前端界面 =====================
st.title("💰 一人财税 · OPC创业者轻量化财税工具")
st.caption("专为单人公司、个体工商户、自由职业者打造 · 零门槛记账 · 自动算税 · 合规提醒")

# 侧边栏导航
# 侧边栏顶部项目信息
st.sidebar.markdown("""
<div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eaecf0; margin-bottom: 20px;">
    <div style="font-size: 40px;">💰</div>
    <h3 style="margin: 8px 0 4px 0; color: #1d2939;">一人财税</h3>
    <p style="font-size: 12px; color: #667085; margin: 0;">OPC创业者财税工具</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.caption("功能导航")

# 菜单按钮列表
menu_items = ["首页介绍", "智能记账", "税额测算", "报表分析", "政策动态"]
for item in menu_items:
    # 当前页面按钮高亮
    if st.session_state["current_page"] == item:
        st.sidebar.button(f"  {item}", key=item, use_container_width=True, type="primary")
    else:
        if st.sidebar.button(f"  {item}", key=item, use_container_width=True):
            st.session_state["current_page"] = item
            st.rerun()

menu = st.session_state["current_page"]

# -------------------- 1. 首页介绍 --------------------
if menu == "首页介绍":
    st.header("项目定位")
    st.write("""
    针对单人创业者、个体工商户、自由职业者「代账成本高、自己报税难、软件太复杂」的核心痛点，
    打造轻量化智能财税工具，以传统代账1/10的价格，实现自动记账、税额精准测算、合规申报提醒。
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="resp-feature-card">
            <div class="resp-feature-label">核心功能1</div>
            <div class="resp-feature-title">智能流水记账</div>
            <div class="resp-feature-desc">账单一键导入，自动分类打标签</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="resp-feature-card">
            <div class="resp-feature-label">核心功能2</div>
            <div class="resp-feature-title">税额自动测算</div>
            <div class="resp-feature-desc">匹配最新政策，精准算税节税</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="resp-feature-card">
            <div class="resp-feature-label">核心功能3</div>
            <div class="resp-feature-title">合规申报提醒</div>
            <div class="resp-feature-desc">申报节点提醒，避免逾期罚款</div>
        </div>
        """, unsafe_allow_html=True)

    # -------------------- 2. 智能记账 --------------------
elif menu == "智能记账":
    st.header("📒 智能流水记账")
    st.write("支持微信/支付宝/银行卡导出的Excel/CSV账单，一键导入自动分类")

    # 文件上传
    uploaded_file = st.file_uploader("上传账单文件（Excel/CSV）", type=["xlsx", "csv"])

    # 1. 优先处理新上传的文件
    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file)
        else:
            df_raw = pd.read_excel(uploaded_file)

        df_processed = process_bill(df_raw)
        # 更新会话 + 本地持久化
        st.session_state["user_bill_data"] = df_processed
        save_bill_to_local(df_processed)
        st.success("✅ 账单处理完成，已自动同步至报表分析")

    # 2. 没有新上传，但已有历史数据，直接展示
    elif "user_bill_data" in st.session_state and not st.session_state["user_bill_data"].empty:
        df_processed = st.session_state["user_bill_data"]
        st.info("📌 已加载历史账单数据，上传新文件将自动覆盖")

    # 3. 完全没有数据，显示示例入口
    else:
        if st.button("加载示例数据体验"):
            sample_data = {
                "交易日期": ["2026-10-01", "2026-10-05", "2026-10-10", "2026-10-15", "2026-10-20"],
                "交易描述": ["技术咨询服务费收款", "购买云服务器", "打车出差", "设计费收款", "打印办公耗材"],
                "交易金额": [8000, 299, 156, 12000, 89]
            }
            df_sample = pd.DataFrame(sample_data)
            df_result = process_bill(df_sample)
            st.session_state["user_bill_data"] = df_result
            save_bill_to_local(df_result)
            st.rerun()

    # 只要有数据就展示明细和汇总
    if "user_bill_data" in st.session_state and not st.session_state["user_bill_data"].empty:
        df_processed = st.session_state["user_bill_data"]

        st.subheader("记账明细")
        st.dataframe(df_processed, use_container_width=True)

        # 收支汇总
        income_total = df_processed[df_processed["大类"] == "收入类"]["交易金额"].sum()
        cost_total = df_processed[df_processed["大类"] == "支出类"]["交易金额"].sum()
        profit = income_total - cost_total

        col1, col2, col3 = st.columns(3)
        col1.metric("总收入", f"¥ {income_total:,.2f}")
        col2.metric("总支出", f"¥ {cost_total:,.2f}")
        col3.metric("净利润", f"¥ {profit:,.2f}")

        # 导出按钮
        st.download_button(
            "导出记账报表",
            df_processed.to_csv(index=False).encode("utf-8-sig"),
            "一人财税-记账报表.csv",
            "text/csv"
        )

    else:
        # 示例数据演示
        if st.button("加载示例数据体验"):
            sample_data = {
                "交易日期": ["2026-10-01", "2026-10-05", "2026-10-10", "2026-10-15", "2026-10-20"],
                "交易描述": ["技术咨询服务费收款", "购买云服务器", "打车出差", "设计费收款", "打印办公耗材"],
                "交易金额": [8000, 299, 156, 12000, 89]
            }
            df_sample = pd.DataFrame(sample_data)
            df_result = process_bill(df_sample)
            st.session_state["demo_df"] = df_result
            st.session_state["user_bill_data"] = df_result
            save_bill_to_local(df_result)
            st.rerun()

        if "demo_df" in st.session_state:
            st.dataframe(st.session_state["demo_df"], use_container_width=True)

# -------------------- 3. 税额测算 --------------------
elif menu == "税额测算":
    st.header("🧮 税额精准测算")
    st.caption("基于小规模纳税人/个体工商户最新政策，自动计算并给出节税建议")

    col1, col2 = st.columns(2)
    with col1:
        month_income = st.number_input("月度营业收入（元）", min_value=0, value=80000, step=1000)
    with col2:
        month_cost = st.number_input("月度成本支出（元）", min_value=0, value=20000, step=1000)

    if st.button("开始测算"):
        tax_result = calculate_tax(month_income, month_cost)

        st.subheader("测算结果")
        res_df = pd.DataFrame({
            "税种": tax_result.keys(),
            "金额（元）": tax_result.values()
        })
        st.table(res_df)

        # 节税提醒
        st.info("💡 节税建议：当前月度收入低于10万增值税起征点，免征增值税；"
                "合规留存成本票据，可降低经营所得税应纳税所得额。")

# -------------------- 4. 报表分析 --------------------
elif menu == "报表分析":
    st.header("📊 经营数据报表")

    # 优先读取用户上传的真实账单数据
    if "user_bill_data" in st.session_state and not st.session_state["user_bill_data"].empty:
        df = st.session_state["user_bill_data"].copy()

        # 先处理日期，生成月份列
        df["交易日期"] = pd.to_datetime(df["交易日期"], errors="coerce")
        df["月份"] = df["交易日期"].dt.strftime("%Y-%m")
        df = df.dropna(subset=["月份"])  # 过滤日期无效的行

        # 按月统计收入、支出
        monthly_income = df[df["大类"] == "收入类"].groupby("月份")["交易金额"].sum().reset_index()
        monthly_income = monthly_income.rename(columns={"交易金额": "营业收入"})

        monthly_cost = df[df["大类"] == "支出类"].groupby("月份")["交易金额"].sum().reset_index()
        monthly_cost = monthly_cost.rename(columns={"交易金额": "成本支出"})

        # 合并数据，缺失值补0
        report_df = pd.merge(monthly_income, monthly_cost, on="月份", how="outer")
        report_df = report_df.fillna(0)
        report_df["净利润"] = report_df["营业收入"] - report_df["成本支出"]
        report_df = report_df.sort_values("月份").reset_index(drop=True)

        # 成本结构统计
        cost_structure = df[df["大类"] == "支出类"].groupby("明细分类")["交易金额"].sum().reset_index()
        cost_structure.columns = ["成本分类", "金额"]

        st.caption("📌 基于您上传的账单自动生成")
    else:
        # 没有上传数据时，显示默认示例
        st.caption("📌 当前为示例数据，上传账单后将自动生成专属报表")
        months = [f"2026-{str(i).zfill(2)}" for i in range(1, 11)]
        income_data = [75000, 82000, 78000, 95000, 88000, 92000, 105000, 98000, 110000, 102000]
        cost_data = [18000, 22000, 20000, 25000, 23000, 24000, 28000, 26000, 30000, 27000]
        report_df = pd.DataFrame({
            "月份": months,
            "营业收入": income_data,
            "成本支出": cost_data
        })
        report_df["净利润"] = report_df["营业收入"] - report_df["成本支出"]

        cost_structure = pd.DataFrame({
            "成本分类": ["办公成本", "差旅交通", "营销推广", "人力成本", "其他"],
            "金额": [5000, 3000, 8000, 6000, 5000]
        })

    # 收支趋势图
    fig_trend = px.line(report_df, x="月份", y=["营业收入", "成本支出", "净利润"],
                        title="月度收支趋势", markers=True,
                        color_discrete_sequence=["#165DFF", "#F53F3F", "#00B42A"],
                        template="plotly_white")
    st.plotly_chart(fig_trend, use_container_width=True)

    # 成本结构饼图
    fig_pie = px.pie(cost_structure, values="金额", names="成本分类", title="成本结构占比",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_pie, use_container_width=True)


# -------------------- 5. 政策动态 --------------------
elif menu == "政策动态":
    st.header("📑 最新财税政策动态")
    st.caption("自动采集官方公开政策，实时更新规则库，确保算税规则精准")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🔄 刷新政策库"):
            with st.spinner("正在采集最新政策..."):
                try:
                    crawler = TaxPolicyCrawler()
                    policies = crawler.run_crawler(max_count=6)
                    st.session_state["policies"] = policies
                    st.session_state["policy_update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.success(f"✅ 更新成功，共采集 {len(policies)} 条政策")
                except Exception as e:
                    st.error(f"❌ 采集失败：{str(e)}")

    # 显示更新时间
    if "policy_update_time" in st.session_state:
        st.caption(f"📅 最后更新时间：{st.session_state['policy_update_time']}")

    # 展示政策列表
    if "policies" not in st.session_state:
        if os.path.exists("tax_policy_library.json"):
            with open("tax_policy_library.json", "r", encoding="utf-8") as f:
                st.session_state["policies"] = json.load(f)
            st.info("📂 已加载本地缓存的政策库")
        else:
            st.info("点击左侧按钮，采集最新财税政策")

    if "policies" in st.session_state and len(st.session_state["policies"]) > 0:
        for p in st.session_state["policies"]:
            with st.expander(f"📌 {p['title']}"):
                st.caption(f"发布日期：{p['pub_date']} | 标签：{'、'.join(p['tags'])}")
                st.write(p["content_summary"])
                st.markdown(f"[查看原文]({p['url']})")


# 页脚
st.sidebar.divider()
st.sidebar.caption("第六届全国大学生技术创新创业大赛 · OPC赛道参赛项目")
