______________________________________________________________________

## name: dummy-weather description: 指定された地域のダミーの天気を返します。 version: 1.0.0

# Dummy Weather Skill

このスキルは、実際には気象 API を呼び出さず、ランダムなダミーの天気情報を返します。

## Usage

```python
import random

def get_weather(location):
    weathers = ["晴れ", "曇り", "雨", "雪"]
    temp = random.randint(10, 25)
    return f"{location}の天気は{random.choice(weathers)}、気温は{temp}度です。"

if __name__ == "__main__":
    import sys
    loc = sys.argv[1] if len(sys.argv) > 1 else "東京"
    print(get_weather(loc))
```
