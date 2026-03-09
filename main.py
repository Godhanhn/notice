import time
import json
import os
import requests
import datetime
import akshare as ak
import logging
import traceback

# 设置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 飞书 Webhook 地址
WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/e5d0457e-e082-4174-ba17-fc6cdcd7f8d5"

# 数据持久化配置
DATA_DIR = "data"
STATE_FILE = os.path.join(DATA_DIR, "seen_notices.json")
STOCKS_FILE = os.path.join(DATA_DIR, "stocks.json")
MAPPING_FILE = os.path.join(DATA_DIR, "stock_mapping.json")

# 默认监控公司
DEFAULT_STOCKS = {
    "600884": "杉杉股份",
    "002785": "万里石",
    "002849": "威星智能",
    "300132": "青松股份"
}

# 轮询间隔（秒）
POLL_INTERVAL = 600

def load_stocks():
    """加载需要监控的股票列表"""
    if not os.path.exists(STOCKS_FILE):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        with open(STOCKS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_STOCKS, f, ensure_ascii=False, indent=2)
        return DEFAULT_STOCKS
    try:
        with open(STOCKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"加载股票配置失败: {e}")
        return DEFAULT_STOCKS

def update_stock_mapping():
    """定期更新A股所有的股票代码和名称映射，供网页端搜索使用"""
    try:
        # 获取所有A股代码和名称
        df = ak.stock_info_a_code_name()
        mapping = {}
        for _, row in df.iterrows():
            code = str(row['code'])
            name = str(row['name'])
            mapping[code] = name
        
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        with open(MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False)
        logging.info("成功更新A股代码名称映射。")
    except Exception as e:
        logging.error(f"更新A股代码名称映射失败: {e}")

def load_seen_notices():
    """加载已推送的公告记录"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载状态文件失败: {e}")
    return {}

def save_seen_notices(seen):
    """保存已推送的公告记录"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存状态文件失败: {e}")

def is_important_notice(title):
    keywords = [
        '实控人', '实际控制人', '控制权', 
        '定增', '向特定对象发行', 
        '资产收购', '收购资产', '购买资产', '重大资产重组', '要约收购',
        '权益变动',  
        '立案', '冻结', '违规', '处罚', '问询', '关注函', '监管函'
    ]
    return any(kw in title for kw in keywords)

def update_stock_history_data(symbol, name):
    """更新股票的历史日线数据，用于网页端K线图展示"""
    history_file = os.path.join(DATA_DIR, "stock_history.json")
    all_history = {}
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                all_history = json.load(f)
        except:
            pass
            
    today = datetime.datetime.now()
    start_date = (today - datetime.timedelta(days=180)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")
    
    try:
        # 获取前复权历史数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        if not df.empty:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row['日期'])[:10],
                    "open": float(row['开盘']),
                    "close": float(row['收盘']),
                    "high": float(row['最高']),
                    "low": float(row['最低']),
                    "volume": float(row['成交量'])
                })
            all_history[symbol] = {
                "name": name,
                "history": records
            }
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(all_history, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"获取 {name} ({symbol}) 历史数据失败: {e}")

def update_latest_notices_file(symbol, name, df):
    """更新最新公告的详情到 JSON 文件中，供网页展示使用"""
    latest_file = os.path.join(DATA_DIR, "latest_notices.json")
    
    # 加载已有的最新公告数据
    all_latest = {}
    if os.path.exists(latest_file):
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                all_latest = json.load(f)
        except:
            pass
            
    # 取最新的前20条（默认展示10条，点击更多展示后10条）
    records = []
    for _, row in df.iterrows():
        title = row.get("公告标题", "")
        records.append({
            "title": title,
            "time": row.get("公告时间", ""),
            "link": row.get("公告链接", ""),
            "important": is_important_notice(title)
        })
        
    all_latest[symbol] = {
        "name": name,
        "notices": records[:20]
    }
    
    try:
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(all_latest, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存最新公告文件失败: {e}")

def send_feishu_message(stock_name, title, pub_time, link, is_important=False):
    """发送飞书机器人卡片通知"""
    header_title = f"📈 【新公告提醒】{stock_name}"
    header_template = "blue"
    
    if is_important:
        header_title = f"🚨 【重大事项提醒】{stock_name}"
        header_template = "red"
        
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": header_title
                },
                "template": header_template
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**标题：**[{title}]({link})\n**时间：**{pub_time}"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "查看详情"
                            },
                            "type": "primary",
                            "url": link
                        }
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code != 200:
            logging.error(f"飞书消息发送失败，响应码: {response.status_code}, 响应内容: {response.text}")
        else:
            logging.info(f"成功发送通知: {stock_name} - {title}")
    except Exception as e:
        logging.error(f"请求飞书 Webhook 时发生异常: {e}")

def get_latest_announcements(symbol, start_date, end_date):
    """获取指定股票在时间段内的最新公告，返回最多10条记录"""
    df = ak.stock_zh_a_disclosure_report_cninfo(
        symbol=symbol,
        market="沪深京",
        start_date=start_date,
        end_date=end_date
    )
    if df.empty:
        return df
    # 按公告时间降序排列，取前30条（给网页足够的数据缓存）
    df = df.sort_values(by="公告时间", ascending=False).head(30)
    return df

def initialize_state():
    """首次运行初始化：仅记录近期的前10条公告作为已读，不发送推送，避免启动时消息轰炸"""
    logging.info("未发现历史状态文件，开始初始化并抓取历史数据作为已读基准...")
    seen_notices = {}
    
    today = datetime.datetime.now()
    start_date = (today - datetime.timedelta(days=180)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")
    
    current_stocks = load_stocks()
    for symbol, name in current_stocks.items():
        seen_notices[symbol] = []
        try:
            df = get_latest_announcements(symbol, start_date, end_date)
            if not df.empty:
                for _, row in df.iterrows():
                    link = row.get("公告链接", "")
                    if link:
                        seen_notices[symbol].append(link)
            logging.info(f"初始化完成: {name} ({symbol})，已记录 {len(seen_notices[symbol])} 条历史公告。")
        except Exception as e:
            logging.error(f"初始化 {name} ({symbol}) 时发生错误: {e}")
            
    save_seen_notices(seen_notices)
    logging.info("初始化完毕，即将进入轮询监控。")

def check_announcements():
    """主检测逻辑"""
    seen_notices = load_seen_notices()
    
    # 获取公告的时间范围：为了避免错漏，我们每次抓取过去180天到今天的公告（因为可能长时间没有发公告，保证能取到最近10条）
    today = datetime.datetime.now()
    start_date = (today - datetime.timedelta(days=180)).strftime("%Y%m%d")
    end_date = today.strftime("%Y%m%d")
    
    current_stocks = load_stocks()
    for symbol, name in current_stocks.items():
        logging.info(f"正在获取 {name} ({symbol}) 的公告...")
        try:
            df = get_latest_announcements(symbol, start_date, end_date)
            
            if df.empty:
                logging.info(f"{name} 在查询时间内没有公告记录。")
                continue
                
            is_first_time = symbol not in seen_notices
            if is_first_time:
                seen_notices[symbol] = []
                
            has_new = False
            for _, row in df.iterrows():
                link = row.get("公告链接", "")
                title = row.get("公告标题", "")
                pub_time = row.get("公告时间", "")
                
                if not link:
                    continue
                    
                # 以链接作为公告的唯一标识
                notice_id = link
                
                if notice_id not in seen_notices[symbol]:
                    has_new = True
                    # 只有非首次拉取才发送飞书通知，第一次拉取仅做基准记录
                    if not is_first_time:
                        send_feishu_message(name, title, pub_time, link, is_important_notice(title))
                    # 记录为已推
                    seen_notices[symbol].append(notice_id)
            
            if not has_new:
                logging.info(f"{name} 暂无新公告。")
                
            # 维护状态列表大小，防止文件无限增长（保留最新100条）
            seen_notices[symbol] = seen_notices[symbol][-100:]
            
            # 更新最新公告数据以便前端网页展示
            update_latest_notices_file(symbol, name, df)
            
            # 更新K线历史数据
            update_stock_history_data(symbol, name)
            
        except Exception as e:
            logging.error(f"获取或处理 {name} ({symbol}) 公告时发生错误:\n{traceback.format_exc()}")
            
    # 保存最新状态
    save_seen_notices(seen_notices)

def update_single_stock(symbol, name):
    """单独更新某一只股票的公告信息"""
    logging.info(f"正在快速获取新增股票 {name} ({symbol}) 的公告...")
    try:
        today = datetime.datetime.now()
        start_date = (today - datetime.timedelta(days=180)).strftime("%Y%m%d")
        end_date = today.strftime("%Y%m%d")
        
        df = get_latest_announcements(symbol, start_date, end_date)
        
        if df.empty:
            logging.info(f"{name} 在查询时间内没有公告记录。")
            # 即使为空也写入网页展示文件，以免一直没记录
            update_latest_notices_file(symbol, name, df)
            return
            
        seen_notices = load_seen_notices()
        if symbol not in seen_notices:
            seen_notices[symbol] = []
            
        # 对于新加的股票，为了避免初次加入时产生大量飞书推送，我们将它们直接记入已读
        for _, row in df.iterrows():
            link = row.get("公告链接", "")
            if link and link not in seen_notices[symbol]:
                seen_notices[symbol].append(link)
                
        # 维护状态列表大小
        seen_notices[symbol] = seen_notices[symbol][-100:]
        
        # 更新最新公告数据以便前端网页展示
        update_latest_notices_file(symbol, name, df)
        
        # 更新K线历史数据
        update_stock_history_data(symbol, name)
        
        save_seen_notices(seen_notices)
        
        logging.info(f"{name} ({symbol}) 公告数据已快速同步完毕。")
    except Exception as e:
        logging.error(f"获取 {name} ({symbol}) 公告时发生错误:\n{traceback.format_exc()}")

def main():
    logging.info("AkShare 公告监控服务启动...")
    
    # 启动时更新一次A股映射数据
    update_stock_mapping()
    
    if not os.path.exists(STATE_FILE):
        initialize_state()
        
    last_check_time = 0
    last_stocks_mtime = 0
        
    while True:
        try:
            current_mtime = 0
            if os.path.exists(STOCKS_FILE):
                current_mtime = os.path.getmtime(STOCKS_FILE)
                
            current_time = time.time()
            
            # 距离上次检查超过了轮询间隔，进行全量检查
            if current_time - last_check_time >= POLL_INTERVAL:
                check_announcements()
                last_check_time = time.time()
                last_stocks_mtime = current_mtime
                
            # 股票配置发生了变化（新增或删除）
            elif current_mtime != last_stocks_mtime and last_stocks_mtime != 0:
                logging.info("检测到监控股票列表发生变化，检查差异...")
                
                # 读取新老状态对比
                try:
                    new_stocks = load_stocks()
                    latest_file = os.path.join(DATA_DIR, "latest_notices.json")
                    existing_stocks = []
                    if os.path.exists(latest_file):
                        with open(latest_file, "r", encoding="utf-8") as f:
                            existing_stocks = list(json.load(f).keys())
                    
                    for symbol, name in new_stocks.items():
                        if symbol not in existing_stocks:
                            # 发现了新增的股票，立即单点更新
                            update_single_stock(symbol, name)
                except Exception as e:
                    pass
                    
                last_stocks_mtime = current_mtime
                
        except Exception as e:
            logging.error(f"执行轮询任务时发生未知异常:\n{traceback.format_exc()}")
            
        # 短暂休眠，以便快速响应配置文件的变化
        time.sleep(5)

if __name__ == "__main__":
    main()
