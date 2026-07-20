# Yuu on Fluxer

Fluxer で動くBotちゃん

## 動作環境

| 項目 | 要件 |
| --- | --- |
| Python | 3.12 以上（コード内で f-string 内への `"` のネスト（PEP 701）を使用しているため） |

## 依存パッケージ

| パッケージ | 用途 |
| --- | --- |
| [`fluxer.py`](https://pypi.org/project/fluxer.py/) | Fluxer Bot の本体（`Client` / イベント処理） |
| `requests` | 天気情報など外部APIへのHTTPリクエスト |
| `beautifulsoup4` | `web_scraping()` でのHTMLパース |
| `jaconv` | ひらがな・カタカナ⇔モールス信号変換時の文字変換 |
| `psutil` | `health` コマンドでのCPU/メモリ使用率取得 |

インストールは以下の通りです。

```bash
pip install fluxer.py[voice] requests beautifulsoup4 jaconv psutil
```

## 設定ファイル

`config/config.json` に以下のキーを用意してください。

| キー | 型 | 説明 |
| --- | --- | --- |
| `adminID` | `int` | 管理者のユーザーID（起動通知・メンション表示に使用） |
| `autoAllowChannel` | `int[]` | 定時通知を送るチャンネルIDのリスト |
| `emotionFile` | `str` | 応答用SQLiteデータベースへの相対パス |
| `eventFilePath` | `str` | 記念日データ（`event.json`）への相対パス |
| `README` | `str` | `$prof` コマンドで返す README への相対パス |
| `tempFile` | `str` | 状態保存用一時ファイルへの相対パス |

また、`config/fluxer.token` にBotのトークンを1行目に記述してください。