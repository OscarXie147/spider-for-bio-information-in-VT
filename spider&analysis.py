from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
from openai import OpenAI


# 浏览器配置
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 初始化浏览器
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)


def get_faculty_links():
    """获取所有教师个人页面链接（修复版）"""
    print("正在收集教师个人页面链接...")
    try:
        driver.get("https://bit.vt.edu/faculty/directory.html")

        # 显式等待+重试机制
        container = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR,
                                            'div.vt-list-columns.vt-num-col-6'))
        )

        # 使用更宽松的选择器
        items = container.find_elements(By.CSS_SELECTOR, 'li a.vt-list-item-title-link')

        links = []
        for item in items:
            try:
                href = item.get_attribute('href')
                if not href.startswith('http'):
                    href = f"https://bit.vt.edu{href}"
                links.append(href)
                print(f"发现链接：{href}")
            except Exception as e:
                print(f"链接提取失败：{str(e)}")
                continue

        print(f"共发现{len(links)}个有效链接")
        return links

    except Exception as e:
        print(f"关键错误：{str(e)}")
        return []

def scrape_profile(url):
    """抓取单个教师详细信息"""
    driver.get(url)
    time.sleep(1)  # 基础等待

    profile = {'url': url, 'name': '', 'email': '', 'bio': ''}

    try:
        # 提取姓名
        name_element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.vt-bio-info h1.vt-bio-name'))
        )
        profile['name'] = name_element.text.strip()
    except:
        print(f"[{url}] 未找到姓名")

    try:
        # 提取邮箱
        email_div = driver.find_element(By.CSS_SELECTOR, 'div.vt-bio-email')
        profile['email'] = email_div.find_element(By.TAG_NAME, 'a').text.strip()
    except:
        print(f"[{url}] 未找到邮箱")

    try:
        # ===== 新版多容器介绍提取 =====
        content_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.vt-bodycol-content'))
        )

        # 定位所有vt-text容器
        text_divs = content_container.find_elements(By.CSS_SELECTOR, 'div.vt-text')

        all_paragraphs = []
        for div in text_divs:
            # 提取当前div内的所有段落
            paragraphs = div.find_elements(By.TAG_NAME, 'p')
            clean_text = [p.text.strip() for p in paragraphs if p.text.strip()]
            if clean_text:
                all_paragraphs.extend(clean_text)

        profile['bio'] = '\n\n'.join(all_paragraphs) if all_paragraphs else '暂无介绍'

        # 调试输出
        print(f"[{url}] 发现 {len(text_divs)} 个文本容器，提取到 {len(all_paragraphs)} 个段落")

    except Exception as e:
        print(f"[{url}] 介绍提取失败: {str(e)}")
        profile['bio'] = '提取失败'
    return profile

def generate_summary(text): 

    client = OpenAI(
        api_key="your_api_key",
        base_url="https://api.openai.com"
    )   
    # 设置 API 基础地址和密钥
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"以下内容是教师简介，请总结出教师的研究方向和研究成果：{text}"}],
        temperature=0.5,
    )
    return response.choices[0].message.content  

# 主程序
if __name__ == "__main__":
    try:
        # 第一步：获取所有教师个人页面链接
        all_links = get_faculty_links()

        if not all_links:
            print("未获取到任何链接，请检查网络或页面结构！")
            exit()

        # 第二步：遍历所有链接抓取详细信息
        final_data = []
        for idx, link in enumerate(all_links, 1):
            print(f"正在处理第{idx}/{len(all_links)}个页面: {link}")
            final_data.append(scrape_profile(link))
            # 第三步：生成总结
            summary = generate_summary(final_data[-1]['bio'])
            final_data[-1]['summary'] = summary

        # 保存结果
        with open('vt_faculty_details.csv', 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'url', 'email', 'bio', 'summary'])
            writer.writeheader()
            writer.writerows(final_data)

        print(f"\n数据采集完成！共保存{len(final_data)}条记录")
    finally:
        driver.quit()



