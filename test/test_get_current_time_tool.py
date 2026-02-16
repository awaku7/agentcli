import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/scheck"))
)
import unittest
import datetime
from uagent.tools.get_current_time_tool import run_tool


class TestGetCurrentTimeTool(unittest.TestCase):
    def test_get_current_time_format(self):
        """ISO 8601 形式で時刻が返るか"""
        result = run_tool({})
        self.assertIn("[get_current_time]", result)
        # 時刻部分を抽出 (ISO format: YYYY-MM-DDTHH:MM:SS.mmmmmm)
        time_str = result.split("ISO8601 (Local): ")[1].split("\n")[0].strip()
        try:
            # 形式チェック
            datetime.datetime.fromisoformat(time_str)
        except ValueError:
            self.fail(f"Invalid ISO format: {time_str}")

    def test_get_current_time_accuracy(self):
        """現在時刻と大きくズレていないか"""
        result = run_tool({})
        time_str = result.split("ISO8601 (Local): ")[1].split("\n")[0].strip()
        dt = datetime.datetime.fromisoformat(time_str)
        now = datetime.datetime.now().astimezone()
        # 実行のわずかなラグを考慮して、1分以内であればOKとする
        diff = abs((now - dt).total_seconds())
        self.assertLess(diff, 60)


if __name__ == "__main__":
    unittest.main()
