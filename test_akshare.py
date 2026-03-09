import akshare as ak
import sys
import datetime

sys.stdout.reconfigure(encoding='utf-8')

def test_akshare():
    print("Testing stock_zh_a_disclosure_report_cninfo with correct format")
    try:
        # 杉杉股份 latest announcements
        df = ak.stock_zh_a_disclosure_report_cninfo(symbol="600884", market="沪深京", start_date="20260201", end_date="20260302")
        print("Data length:", len(df))
        if len(df) > 0:
            print("Max date:", df['公告时间'].max())
            print(df.head(2).to_json(orient="records", force_ascii=False))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_akshare()
