import main

def test_feishu():
    print("Testing Feishu Webhook...")
    main.send_feishu_message(
        stock_name="测试公司 (000000)",
        title="关于公司进行Feishu通知测试的公告",
        pub_time="2026-03-02 12:00:00",
        link="http://www.cninfo.com.cn/new/index"
    )
    print("Test complete. Check your Feishu channel.")

if __name__ == "__main__":
    test_feishu()
