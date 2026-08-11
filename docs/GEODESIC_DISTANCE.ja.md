# 直線距離

`geodesic_distance` は、2点の緯度・経度からHaversine式で直線距離を計算します。

## 入力

- `lat_a`、`lon_a`: 地点Aの緯度・経度
- `lat_b`、`lon_b`: 地点Bの緯度・経度
- `resolve_addresses`: `true` の場合、OpenStreetMap Nominatimで両地点の住所も取得
- `language`: 住所取得時の任意の言語

## 出力

`distance_km`、`distance_m`、初期方位角、計算方式を返します。座標が分かっている場合、住所解決は不要です。

これは地理上の直線距離であり、道路距離や公共交通機関の経路距離ではありません。NominatimへのアクセスはOpenStreetMapの利用ポリシーとレート制限に従います。
