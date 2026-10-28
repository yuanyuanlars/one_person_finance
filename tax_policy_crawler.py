import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime


class TaxPolicyCrawler:
    """
    财税政策公开爬虫：采集国家税务总局政策文件
    仅用于学习参赛演示，遵守网站robots协议，控制请求频率
    """

    def __init__(self):
        self.base_url = "http://www.chinatax.gov.cn"
        # 政策列表页（国家税务总局-最新政策栏目）
        self.list_url = f"{self.base_url}/chinatax/n810341/n810755/common_list.shtml"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        # 政策分类关键词（用于自动打标签）
        self.classify_keywords = {
            "增值税": ["增值税", "小规模纳税人", "进项抵扣", "税率"],
            "个人所得税": ["个税", "个人所得税", "经营所得", "减除费用"],
            "企业所得税": ["企业所得税", "汇算清缴", "小微企业", "税前扣除"],
            "税费优惠": ["减免", "优惠", "免征", "减征", "退税"],
            "申报办税": ["申报", "报税", "征期", "电子税务局", "年报"]
        }

    def fetch_policy_list(self, max_count=10):
        """
        抓取最新政策列表：标题、发布日期、详情链接
        """
        policy_list = []
        try:
            resp = requests.get(self.list_url, headers=self.headers, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            # 解析列表项（适配页面结构）
            items = soup.select("ul.list li")
            for item in items[:max_count]:
                a_tag = item.select_one("a")
                date_tag = item.select_one("span")
                if not a_tag:
                    continue

                title = a_tag.get_text(strip=True)
                link = a_tag.get("href", "")
                # 补全相对链接
                if link.startswith("/"):
                    link = self.base_url + link
                pub_date = date_tag.get_text(strip=True) if date_tag else ""

                policy_list.append({
                    "title": title,
                    "url": link,
                    "pub_date": pub_date,
                    "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                # 控制请求频率，避免给站点造成压力
                time.sleep(0.5)

        except Exception as e:
            print(f"抓取列表失败: {e}")
        return policy_list

    def classify_policy(self, title, content=""):
        """
        根据标题和正文关键词自动给政策分类打标签
        """
        tags = []
        text = title + content
        for category, keywords in self.classify_keywords.items():
            for kw in keywords:
                if kw in text:
                    tags.append(category)
                    break
        return tags if tags else ["其他政策"]

    def fetch_policy_detail(self, policy_item):
        """
        抓取单篇政策的正文内容
        """
        try:
            resp = requests.get(policy_item["url"], headers=self.headers, timeout=10)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")

            # 提取正文（适配常见正文容器）
            content = ""
            content_box = soup.select_one("div.content") or soup.select_one("div.article")
            if content_box:
                # 去除多余标签，只保留文本
                for tag in content_box.select(["script", "style", "table"]):
                    tag.decompose()
                content = content_box.get_text(strip=True, separator="\n")
                # 控制长度
                content = content[:2000]

            # 自动分类
            policy_item["tags"] = self.classify_policy(policy_item["title"], content)
            policy_item["content_summary"] = content[:300] + "..." if len(content) > 300 else content

        except Exception as e:
            policy_item["content_summary"] = "正文获取失败"
            policy_item["tags"] = ["其他政策"]

        time.sleep(0.8)
        return policy_item

    def save_to_json(self, data, filename="tax_policy_library.json"):
        """
        保存结构化政策库到本地JSON文件，可对接规则引擎
        """
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 政策库已保存至 {filename}，共 {len(data)} 条")

    def run_crawler(self, max_count=8):
        """
        执行完整爬取流程
        """
        print("🔍 开始采集最新财税政策...")
        # 1. 获取列表
        policy_list = self.fetch_policy_list(max_count)
        if not policy_list:
            print("❌ 未获取到政策列表")
            return []

        # 2. 抓取详情并分类
        full_policies = []
        for idx, item in enumerate(policy_list, 1):
            print(f"正在处理第 {idx}/{len(policy_list)} 条：{item['title']}")
            full_item = self.fetch_policy_detail(item)
            full_policies.append(full_item)

        # 3. 保存
        self.save_to_json(full_policies)
        return full_policies


# ===================== 直接运行测试 =====================
if __name__ == "__main__":
    crawler = TaxPolicyCrawler()
    policies = crawler.run_crawler(max_count=6)

    # 打印结果预览
    print("\n📋 采集结果预览：")
    for p in policies:
        print(f"[{p['pub_date']}] {p['title']} | 标签：{','.join(p['tags'])}")
