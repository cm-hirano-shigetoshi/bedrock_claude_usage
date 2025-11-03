# AWS Bedrock CloudWatch メトリクス取得ツール

AWS Bedrockの各種トークンメトリクスをCloudWatchから取得するCLIツールです。

## 機能

- 指定期間のBedrockモデルのトークン使用量を取得
- 複数のメトリクスを同時に取得・表示
  - 入力トークン数 (InputTokenCount)
  - 出力トークン数 (OutputTokenCount)
  - キャッシュ書き込みトークン数 (CacheWriteInputTokenCount)
  - キャッシュ読み込みトークン数 (CacheReadInputTokenCount)
- 日単位での集計表示
- 各メトリクスの総計を計算
- **料金計算機能**
  - 各トークンタイプごとの料金を自動計算
  - 日別および総合計金額を表示
- AWSプロファイルとリージョンの柔軟な設定

## 必要要件

- Python 3.8以上
- boto3

## インストール

### GitHubから直接インストール

```bash
pip install git+https://github.com/YOUR_USERNAME/bedrock-metrics.git
```

### ローカルにクローンしてインストール

```bash
git clone https://github.com/YOUR_USERNAME/bedrock-metrics.git
cd bedrock-metrics
pip install .
```

### 開発モードでインストール（編集可能モード）

```bash
git clone https://github.com/YOUR_USERNAME/bedrock-metrics.git
cd bedrock-metrics
pip install -e .
```

## 使用方法

インストール後は `bedrock-metrics` コマンドが使用できます。

### 基本的な使い方

```bash
bedrock-metrics <開始日> <終了日>
```

### 対象モデルと料金設定

対象モデルと料金は `models_config.json` ファイルで管理されています。複数モデルの同時集計が可能で、モデルごとに異なる料金設定ができます。

デフォルト設定（`models_config.json`）:
```json
{
  "models": [
    {
      "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
      "pricing": {
        "input_token": 0.003,
        "output_token": 0.015,
        "cache_write_token": 0.00375,
        "cache_read_token": 0.0003
      }
    },
    ...
  ]
}
```

**注意**:
- モデルの追加・削除・料金変更は `models_config.json` を編集してください
- 料金は1,000トークンあたりのUSD単位で指定します
- 全モデルのデータは日付ごとに自動的に集約され、モデル別の料金で計算されます

### 引数

#### 必須引数

- `start_date`: 開始日付 (形式: YYYY-MM-DD)
- `end_date`: 終了日付 (形式: YYYY-MM-DD)

#### オプション引数

- `--profile`: AWSプロファイル名 (デフォルト: `AWS_PROFILE`環境変数)
- `--region`: AWSリージョン (デフォルト: `AWS_DEFAULT_REGION`環境変数)
- `--json`: JSON形式で標準出力に表示（ファイル保存なし）
- `--output`, `-o`: JSON保存先ファイルパス（`--json`なしの場合のデフォルト: `bedrock_metrics_YYYYMMDD_YYYYMMDD.json`）

### 使用例

```bash
# 基本的な使用（テーブル形式 + JSONファイル保存）
bedrock-metrics 2025-09-12 2025-09-13

# JSON形式で標準出力に表示（ファイル保存なし）
bedrock-metrics 2025-09-12 2025-09-13 --json

# JSON出力をファイルに保存
bedrock-metrics 2025-09-12 2025-09-13 --json > metrics.json

# カスタムファイルパスでJSON保存
bedrock-metrics 2025-09-12 2025-09-13 --output my_metrics.json

# プロファイルを指定
bedrock-metrics 2025-09-12 2025-09-13 --profile myprofile

# リージョンを指定
bedrock-metrics 2025-09-12 2025-09-13 --region us-east-1

# 複数オプションを組み合わせ
bedrock-metrics 2025-09-12 2025-09-13 --json --profile myprofile --region us-west-2
```

### 環境変数での設定

AWSプロファイルとリージョンは環境変数でも設定できます:

```bash
export AWS_PROFILE=myprofile
export AWS_DEFAULT_REGION=us-east-1
bedrock-metrics 2025-09-12 2025-09-13
```

## 出力例

全モデルのデータを日付ごとに集約して表示します。

**表示単位**:
- Input / Output: K単位（1,000トークン）
- Cache Write / Cache Read: M単位（1,000,000トークン）

```
メトリクス取得中...
  開始日: 2024-01-15
  終了日: 2024-01-21
  対象モデル数: 4
  リージョン: us-east-1

  モデル 'us.anthropic.claude-sonnet-4-5-20250929-v1:0' のメトリクスを取得中...
  モデル 'us.anthropic.claude-haiku-4-5-20251001-v1:0' のメトリクスを取得中...
  モデル 'us.anthropic.claude-sonnet-4-20250514-v1:0' のメトリクスを取得中...
  モデル 'us.anthropic.claude-3-5-haiku-20241022-v1:0' のメトリクスを取得中...

============================================================================================================================================
Date         | Input                | Output               | Cache Write          | Cache Read           | Total
--------------------------------------------------------------------------------------------------------------------------------------------
2024-01-15   |    755.0k ($  2.27) |    334.4k ($  5.02) |    1.20M ($  4.50) |    0.42M ($  0.13) |      $11.91
2024-01-16   |  1,250.0k ($  3.75) |    520.8k ($  7.81) |    2.10M ($  7.88) |    0.78M ($  0.23) |      $19.67
2024-01-17   |    360.0k ($  1.08) |    144.0k ($  2.16) |    0.63M ($  2.37) |    0.13M ($  0.04) |       $5.65
2024-01-18   |    890.0k ($  2.67) |    380.0k ($  5.70) |    0.95M ($  3.56) |    0.26M ($  0.08) |      $12.01
2024-01-19   |  1,450.0k ($  4.35) |    610.0k ($  9.15) |    1.80M ($  6.75) |    0.59M ($  0.18) |      $20.43
2024-01-20   |  1,120.0k ($  3.36) |    475.0k ($  7.13) |    1.35M ($  5.06) |    0.45M ($  0.14) |      $15.69
2024-01-21   |  1,280.0k ($  3.84) |    540.0k ($  8.10) |    1.60M ($  6.00) |    0.52M ($  0.16) |      $18.10
--------------------------------------------------------------------------------------------------------------------------------------------
Total        |  7,105.0k ($ 21.32) |  3,004.2k ($ 45.06) |    9.63M ($ 36.12) |    3.14M ($  0.94) |     $103.45
============================================================================================================================================
```

**注意**: 料金は各モデルの設定に基づいて計算されます。料金設定は `models_config.json` で確認・変更できます。

## JSON出力形式

`--json` オプションを使用すると、詳細なデータがJSON形式で出力されます。

### JSON構造

```json
{
  "period": {
    "start": "2024-01-15",
    "end": "2024-01-21"
  },
  "summary": {
    "total_cost": 103.45,
    "input_cost": 21.32,
    "output_cost": 45.06,
    "cache_write_cost": 36.12,
    "cache_read_cost": 0.94
  },
  "by_date": [
    {
      "date": "2024-01-15",
      "total": 11.91,
      "models": [
        {
          "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
          "metrics": {
            "input": {"tokens": 415000, "cost": 1.37},
            "output": {"tokens": 166400, "cost": 2.75},
            "cache_write": {"tokens": 700000, "cost": 2.89},
            "cache_read": {"tokens": 150000, "cost": 0.05}
          },
          "total": 7.06
        },
        {
          "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
          "metrics": {
            "input": {"tokens": 340000, "cost": 0.37},
            "output": {"tokens": 168000, "cost": 0.92},
            "cache_write": {"tokens": 500000, "cost": 0.69},
            "cache_read": {"tokens": 266667, "cost": 0.03}
          },
          "total": 2.01
        }
      ]
    }
  ]
}
```

### JSONフィールドの説明

- `period`: 集計期間
- `summary`: 全期間の合計
  - `total_cost`: 総コスト
  - `input_cost`: 入力トークンの総コスト
  - `output_cost`: 出力トークンの総コスト
  - `cache_write_cost`: キャッシュ書き込みの総コスト
  - `cache_read_cost`: キャッシュ読み込みの総コスト
- `by_date`: 日別のデータ
  - `date`: 日付
  - `total`: その日の総コスト
  - `models`: モデルごとの詳細
    - `model_id`: モデルID
    - `metrics`: メトリクス別のトークン数とコスト
    - `total`: そのモデルのその日の総コスト

## 仕様

- **Period**: 86,400秒 (1日) 固定
- **Statistics**: Sum固定
- **Namespace**: AWS/Bedrock
- **Metrics**:
  - InputTokenCount (入力トークン数)
  - OutputTokenCount (出力トークン数)
  - CacheWriteInputTokenCount (キャッシュ書き込みトークン数)
  - CacheReadInputTokenCount (キャッシュ読み込みトークン数)

## 料金設定のカスタマイズ

料金設定は `models_config.json` で管理されます。モデルごとに異なる料金を設定できます。

### 設定ファイルの構造

```json
{
  "models": [
    {
      "model_id": "モデルID",
      "pricing": {
        "input_token": 入力トークンの料金 (USD/1000トークン),
        "output_token": 出力トークンの料金 (USD/1000トークン),
        "cache_write_token": キャッシュ書き込みの料金 (USD/1000トークン),
        "cache_read_token": キャッシュ読み込みの料金 (USD/1000トークン)
      }
    }
  ]
}
```

### モデルの追加例

```json
{
  "models": [
    {
      "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
      "pricing": {
        "input_token": 0.003,
        "output_token": 0.015,
        "cache_write_token": 0.00375,
        "cache_read_token": 0.0003
      }
    },
    {
      "model_id": "新しいモデルID",
      "pricing": {
        "input_token": 0.005,
        "output_token": 0.020,
        "cache_write_token": 0.00500,
        "cache_read_token": 0.0005
      }
    }
  ]
}
```

**注意**: 料金は予告なく変更される可能性があります。最新の料金については[AWS公式ドキュメント](https://aws.amazon.com/bedrock/pricing/)をご確認ください。

## エラーハンドリング

ツールは以下のエラーを適切に処理します:

- 無効な日付形式
- 開始日が終了日より後
- AWS認証情報の不足
- リージョンの未指定
- CloudWatch APIエラー

## 必要なIAMアクセス許可

このツールを使用するには、以下のIAMアクセス許可が必要です:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

## トラブルシューティング

### データが表示されない場合

- スクリプト内の `MODEL_IDS` 定数に設定されているモデル名が正しいか確認
- 指定した期間にモデルの使用実績があるか確認
- AWSリージョンが正しいか確認 (Bedrockはリージョン依存)

### モデルを追加・変更したい場合

`models_config.json` ファイルを編集してください:

1. モデルを追加する場合は、`models` 配列に新しいエントリを追加
2. モデルを削除する場合は、該当するエントリを削除
3. 料金を変更する場合は、`pricing` の値を更新

### 設定ファイルが見つからない場合

スクリプト実行時に以下のエラーが表示される場合:
```
設定ファイルが見つかりません: /path/to/models_config.json
```

パッケージインストール後は、設定ファイルはパッケージ内に含まれています。カスタム設定を使用したい場合は、実行ディレクトリに `models_config.json` を配置してください。

### 認証エラーの場合

- AWS認証情報が正しく設定されているか確認
- `--profile`オプションまたは`AWS_PROFILE`環境変数を設定

### リージョンエラーの場合

- `--region`オプションまたは`AWS_DEFAULT_REGION`環境変数を設定
- Bedrockがそのリージョンでサポートされているか確認
