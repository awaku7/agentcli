# quantities / 単位付き計算

`quantities` ツールは、[Pint](https://pint.readthedocs.io/) を使って単位変換と物理量の計算を行います。

## インストール

Pint はツールを初めて使用した時に遅延インストールされます。uag の自動依存関係インストーラーを通じて `Pint>=0.24.4` を要求するため、通常の起動時にはインポートもインストールも行いません。

## 使用例

```text
25 degC to degF
```

```text
2.5 kW * 8 hour to kWh
```

```text
1 meter + 20 centimeter to meter
```

`to UNIT` の代わりに任意の `to_unit` 引数も使用できます。`precision` は表示する小数点以下の桁数を指定します（0〜15、既定値6）。

## 安全性と動作

- 式は Pint の物理量式として解析され、任意の Python 実行には対応していません。
- import、`eval`、`exec`、`lambda`、角括弧、波括弧、セミコロンなどの不審な構文は解析前に拒否します。
- 未知の単位や互換性のない変換は、途中結果ではなくローカライズされたエラーを返します。
- ツールは `ok`、`expression`、`result`、`magnitude`、`unit` フィールドを持つ JSON を返します。
- 呼び出しごとに独立した Pint レジストリを作成するため、`x_parallel_safe` に指定されています。

ツールのメタデータとメッセージは、対応するすべてのツールJSONロケールでローカライズされています。
