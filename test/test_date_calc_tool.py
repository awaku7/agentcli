import sys
import os
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)

from tools.date_calc_tool import run_tool


class TestDateCalcTool(unittest.TestCase):
    def test_basic_calc(self):
        """基本的な加算のテスト"""
        # 2024-01-01 + 10日
        result = run_tool({"base_date": "2024-01-01", "days": 10})
        self.assertIn("Result Date: 2024-01-11", result)
        self.assertIn("Thursday", result)

    def test_japanese_holiday(self):
        """日本の祝日判定テスト (holidays利用)"""
        # 2024-01-01 (元旦)
        result = run_tool({"base_date": "2024-01-01", "country": "JP"})
        # holidaysのバージョンや環境により「元日」か「元旦」かが異なる可能性があるため部分一致
        self.assertIn("元", result)

        # 2024-03-20 (春分の日)
        result = run_tool({"base_date": "2024-03-20", "country": "JP"})
        self.assertIn("春分の日", result)

    def test_overseas_holiday(self):
        """海外の祝日判定テスト"""
        # 2024-12-25 (US Christmas)
        result = run_tool({"base_date": "2024-12-25", "country": "US"})
        self.assertIn("Christmas Day", result)

    def test_weekend_handling(self):
        """週末判定テスト"""
        # 2024-05-04 (Saturday)
        result = run_tool({"base_date": "2024-05-04", "country": "JP"})
        self.assertIn("Saturday", result)

    def test_month_overflow(self):
        """月末の処理テスト"""
        # 2024-01-31 + 1ヶ月 -> 2024-02-29 (閏年)
        result = run_tool({"base_date": "2024-01-31", "months": 1})
        self.assertIn("Result Date: 2024-02-29", result)

    def test_error_handling(self):
        """不正な日付形式のテスト"""
        result = run_tool({"base_date": "invalid-date"})
        self.assertIn("Error parsing base_date", result)


if __name__ == "__main__":
    unittest.main()
