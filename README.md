# Notice (A股公告监控服务)

## 简介
这是一个用于实时监控 A 股上市公司最新公告、自动识别重要事项并通过飞书机器人推送提醒的服务项目。项目不仅能自动抓取和通知公告内容，还提供了一个 Web 面板供用户可视化查看公告列表、走势图表并管理监控池。

## 项目架构
本项目主要分为后台数据抓取服务与前台 Web 展示服务两部分：

1. **Python 数据守护进程 (`main.py`)**：
   - 使用 `akshare` 接口定时向全网（巨潮资讯等）查询监控池内股票的最新公告。
   - 自动识别如“实控人变更”、“重组”、“违规处罚”等关键且重要的公告标签。
   - 检测到新公告后，会调用飞书 Webhook (`test_feishu.py` 等演示) 给用户发送实时消息通知。
   - 将最新公告明细、股票历史数据缓存到本地 `data/` 目录的 JSON 文件中（如 `latest_notices.json`、`stock_history.json` 等）。

2. **Go Web 服务 (`web/main.go`)**：
   - 作为一个轻量级的面板服务，专门读取 `data/` 目录下的 JSON 文件缓存。
   - 提供可视化的网页端（基于 `gin` 框架提供接口），供用户快速查看各个股票的公告记录和日线历史图表。
   - 提供增删监控股票的接口，修改结果会自动反馈给 Python 守护进程进行抓取更新。

## 运行与配置

### 1. 启动 Python 爬虫与通知服务
需在 Python 虚拟环境中安装依赖并运行：
```bash
pip install -r requirements.txt
python main.py
```
*注意：可根据需求修改 `main.py` 中 `WEBHOOK_URL` 的飞书 webhook 地址以接收您自己的群内通知。默认每 10 分钟轮询一次。*

### 2. 启动 Go Web 面板
进入 `web` 文件夹并运行 Go 服务：
```bash
cd web
go build -o notice_web main.go
./notice_web
```
启动后访问 `http://localhost:8083` 即可查看可视化面板，管理需要监控的股票代码（如 600884 杉杉股份等）。

### 3. 使用 Docker Compose 部署 (推荐)
本项目提供了编写好的 `docker-compose.yml`，可以将爬虫服务和 Web 面板一键启动，无需在本地配置 Python 或 Go 环境。

在项目根目录下，执行以下命令即可一键启动：
```bash
docker-compose up -d
```
启动后，同样可以通过访问 `http://localhost:8083` 访问 Web 面板。所有数据将被持久化保存在当前目录的 `data/` 文件夹中。

## 声明
本系统爬取的全部内容来自分开提供数据的公共接口，如需频繁请求建议配置代理或适当降低轮询频率。
