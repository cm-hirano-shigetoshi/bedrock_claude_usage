#!/usr/bin/env python3
"""
AWS Bedrock CloudWatch メトリクス取得CLIツール

このツールはAWS Bedrockの各種トークンメトリクスをCloudWatchから取得します。
- InputTokenCount: 入力トークン数
- OutputTokenCount: 出力トークン数
- CacheWriteInputTokenCount: キャッシュ書き込みトークン数
- CacheReadInputTokenCount: キャッシュ読み込みトークン数
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, NoRegionError

# グローバル変数（設定ファイルから読み込み）
MODEL_CONFIGS = []
MODEL_IDS = []
PRICING_BY_MODEL = {}


def load_models_config(config_path: str = "models_config.json") -> None:
    """モデル設定ファイルを読み込み"""
    global MODEL_CONFIGS, MODEL_IDS, PRICING_BY_MODEL

    # スクリプトと同じディレクトリの設定ファイルを探す
    script_dir = Path(__file__).parent
    config_file = script_dir / config_path

    if not config_file.exists():
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {config_file}\n"
            f"models_config.json を作成してください。"
        )

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"設定ファイルのJSON形式が不正です: {e}")

    if "models" not in config_data or not isinstance(config_data["models"], list):
        raise ValueError("設定ファイルに 'models' 配列が必要です")

    MODEL_CONFIGS = config_data["models"]
    MODEL_IDS = [model["model_id"] for model in MODEL_CONFIGS]

    # 各モデルの料金情報を保存
    for model in MODEL_CONFIGS:
        model_id = model["model_id"]
        pricing = model.get("pricing", {})
        PRICING_BY_MODEL[model_id] = {
            "InputTokenCount": pricing.get("input_token", 0.003),
            "OutputTokenCount": pricing.get("output_token", 0.015),
            "CacheWriteInputTokenCount": pricing.get("cache_write_token", 0.00375),
            "CacheReadInputTokenCount": pricing.get("cache_read_token", 0.0003),
        }

    if not MODEL_IDS:
        raise ValueError("設定ファイルにモデルが1つも定義されていません")


def parse_arguments():
    """コマンドライン引数を解析"""
    parser = argparse.ArgumentParser(
        description="AWS Bedrock CloudWatch メトリクスを取得します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s 2025-09-12 2025-09-13  # テーブル表示 + JSONファイル保存
  %(prog)s 2025-09-12 2025-09-13 --profile myprofile
  %(prog)s 2025-09-12 2025-09-13 --region us-east-1
  %(prog)s 2025-09-12 2025-09-13 --output my_metrics.json  # カスタムファイルパス
  %(prog)s 2025-09-12 2025-09-13 --json  # JSON標準出力のみ（ファイル保存なし）
        """,
    )

    parser.add_argument("start_date", help="開始日付 (形式: YYYY-MM-DD)")

    parser.add_argument("end_date", help="終了日付 (形式: YYYY-MM-DD)")

    parser.add_argument(
        "--profile",
        help="AWSプロファイル名 (デフォルト: AWS_PROFILE環境変数)",
        default=os.environ.get("AWS_PROFILE"),
    )

    parser.add_argument(
        "--region",
        help="AWSリージョン (デフォルト: AWS_DEFAULT_REGION環境変数)",
        default=os.environ.get("AWS_DEFAULT_REGION"),
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON形式で標準出力に表示（ファイル保存なし）",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="JSON保存先ファイルパス (--jsonなしの場合のデフォルト: bedrock_claude_usage_YYYYMMDD_YYYYMMDD.json)",
        default=None,
    )

    return parser.parse_args()


def validate_date(date_string: str) -> datetime:
    """日付文字列を検証してdatetimeオブジェクトに変換"""
    try:
        return datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"無効な日付形式です: {date_string}。YYYY-MM-DD形式で指定してください。"
        )


def get_cloudwatch_metrics(
    start_date: str,
    end_date: str,
    profile: Optional[str] = None,
    region: Optional[str] = None,
    quiet: bool = False,
):
    """CloudWatchからBedrockメトリクスを取得（複数モデル対応）"""

    # 日付検証
    start_dt = validate_date(start_date)
    end_dt = validate_date(end_date)

    if start_dt >= end_dt:
        raise ValueError("開始日付は終了日付より前である必要があります。")

    # AWS セッション設定
    session_kwargs = {}
    if profile:
        session_kwargs["profile_name"] = profile
    if region:
        session_kwargs["region_name"] = region

    try:
        session = boto3.Session(**session_kwargs)
        cloudwatch = session.client("cloudwatch")
    except NoCredentialsError:
        raise RuntimeError(
            "AWS認証情報が見つかりません。AWS_PROFILE環境変数を設定するか、"
            "--profileオプションを使用してください。"
        )
    except NoRegionError:
        raise RuntimeError(
            "AWSリージョンが指定されていません。AWS_DEFAULT_REGION環境変数を設定するか、"
            "--regionオプションを使用してください。"
        )

    # 取得するメトリクス一覧
    metric_names = [
        "InputTokenCount",
        "OutputTokenCount",
        "CacheWriteInputTokenCount",
        "CacheReadInputTokenCount",
    ]

    # 全モデルのメトリクスを取得
    all_models_metrics = {}

    for model_id in MODEL_IDS:
        if not quiet:
            print(f"  モデル '{model_id}' のメトリクスを取得中...", file=sys.stderr)
        model_metrics = {}

        for metric_name in metric_names:
            params = {
                "Namespace": "AWS/Bedrock",
                "MetricName": metric_name,
                "StartTime": start_dt.isoformat() + "Z",
                "EndTime": end_dt.isoformat() + "Z",
                "Period": 86400,  # 固定値: 1日
                "Statistics": ["Sum"],  # 固定値
                "Dimensions": [{"Name": "ModelId", "Value": model_id}],
            }

            try:
                response = cloudwatch.get_metric_statistics(**params)
                model_metrics[metric_name] = response
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]
                raise RuntimeError(
                    f"CloudWatch APIエラー ({error_code}): {error_message}"
                )

        all_models_metrics[model_id] = model_metrics

    return all_models_metrics


def calculate_cost(token_count: int, metric_name: str, model_id: str = None) -> float:
    """トークン数から料金を計算（モデル別の料金対応）"""
    if model_id and model_id in PRICING_BY_MODEL:
        price_per_1k = PRICING_BY_MODEL[model_id].get(metric_name, 0)
    else:
        # デフォルト料金（設定ファイルがない場合のフォールバック）
        default_pricing = {
            "InputTokenCount": 0.003,
            "OutputTokenCount": 0.015,
            "CacheWriteInputTokenCount": 0.00375,
            "CacheReadInputTokenCount": 0.0003,
        }
        price_per_1k = default_pricing.get(metric_name, 0)
    return (token_count / 1000) * price_per_1k


def format_output_json(
    all_models_metrics: dict, start_date: str, end_date: str
) -> dict:
    """JSON形式で詳細データを構築して返す"""

    # 日付ごと、モデルごとにデータを整理
    by_date = {}

    for model_id, all_metrics in all_models_metrics.items():
        for metric_name, response in all_metrics.items():
            datapoints = response.get("Datapoints", [])
            for dp in datapoints:
                date_str = dp["Timestamp"].strftime("%Y-%m-%d")
                token_count = int(dp["Sum"])

                # 日付ごとのデータを初期化
                if date_str not in by_date:
                    by_date[date_str] = {}

                # モデルごとのデータを初期化
                if model_id not in by_date[date_str]:
                    by_date[date_str][model_id] = {
                        "input": {"tokens": 0, "cost": 0.0},
                        "output": {"tokens": 0, "cost": 0.0},
                        "cache_write": {"tokens": 0, "cost": 0.0},
                        "cache_read": {"tokens": 0, "cost": 0.0},
                    }

                # メトリクス名をキーに変換
                metric_key_map = {
                    "InputTokenCount": "input",
                    "OutputTokenCount": "output",
                    "CacheWriteInputTokenCount": "cache_write",
                    "CacheReadInputTokenCount": "cache_read",
                }
                metric_key = metric_key_map.get(metric_name)

                if metric_key:
                    by_date[date_str][model_id][metric_key]["tokens"] += token_count
                    cost = calculate_cost(token_count, metric_name, model_id)
                    by_date[date_str][model_id][metric_key]["cost"] += cost

    # 日付でソート
    sorted_dates = sorted(by_date.keys())

    # 総計を計算
    total_cost = 0.0
    total_input_cost = 0.0
    total_output_cost = 0.0
    total_cache_write_cost = 0.0
    total_cache_read_cost = 0.0

    # JSON構造を構築
    by_date_list = []
    for date_str in sorted_dates:
        date_data = {
            "date": date_str,
            "total_cost": 0.0,
            "models": [],
        }

        for model_id, metrics in by_date[date_str].items():
            model_total = (
                metrics["input"]["cost"]
                + metrics["output"]["cost"]
                + metrics["cache_write"]["cost"]
                + metrics["cache_read"]["cost"]
            )

            # モデル別のキャッシュ利用比率を計算
            cache_total_tokens = (
                metrics["cache_write"]["tokens"] + metrics["cache_read"]["tokens"]
            )
            if cache_total_tokens > 0:
                cache_ratio = (
                    metrics["cache_read"]["tokens"] / cache_total_tokens
                ) * 100
            else:
                cache_ratio = 0.0

            model_data = {
                "model_id": model_id,
                "metrics": metrics,
                "cache_ratio": round(cache_ratio, 1),
                "total_cost": round(model_total, 2),
            }

            date_data["models"].append(model_data)
            date_data["total_cost"] += model_total

            # 総計に加算
            total_input_cost += metrics["input"]["cost"]
            total_output_cost += metrics["output"]["cost"]
            total_cache_write_cost += metrics["cache_write"]["cost"]
            total_cache_read_cost += metrics["cache_read"]["cost"]

        date_data["total_cost"] = round(date_data["total_cost"], 2)
        by_date_list.append(date_data)

    total_cost = (
        total_input_cost
        + total_output_cost
        + total_cache_write_cost
        + total_cache_read_cost
    )

    # 全体のキャッシュ利用比率を計算
    total_cache_write_tokens = sum(
        metrics["cache_write"]["tokens"]
        for date_data in by_date_list
        for metrics in [model["metrics"] for model in date_data["models"]]
    )
    total_cache_read_tokens = sum(
        metrics["cache_read"]["tokens"]
        for date_data in by_date_list
        for metrics in [model["metrics"] for model in date_data["models"]]
    )
    total_cache_tokens = total_cache_write_tokens + total_cache_read_tokens
    if total_cache_tokens > 0:
        overall_cache_ratio = (total_cache_read_tokens / total_cache_tokens) * 100
    else:
        overall_cache_ratio = 0.0

    # 最終的なJSON構造
    output_data = {
        "period": {"start": start_date, "end": end_date},
        "summary": {
            "total_cost": round(total_cost, 2),
            "input_cost": round(total_input_cost, 2),
            "output_cost": round(total_output_cost, 2),
            "cache_write_cost": round(total_cache_write_cost, 2),
            "cache_read_cost": round(total_cache_read_cost, 2),
            "cache_ratio": round(overall_cache_ratio, 1),
        },
        "by_date": by_date_list,
    }

    return output_data


def format_output(all_models_metrics: dict):
    """メトリクス結果を整形して表示（全モデル統合版）"""

    # 全モデルのデータを日付ごとに統合（トークン数と料金を別々に集計）
    aggregated_data = {}
    aggregated_costs = {}
    has_any_data = False

    for model_id, all_metrics in all_models_metrics.items():
        for metric_name, response in all_metrics.items():
            datapoints = response.get("Datapoints", [])
            if datapoints:
                has_any_data = True
                for dp in datapoints:
                    date_str = dp["Timestamp"].strftime("%Y-%m-%d")
                    token_count = int(dp["Sum"])

                    # トークン数を集計
                    if date_str not in aggregated_data:
                        aggregated_data[date_str] = {
                            "InputTokenCount": 0,
                            "OutputTokenCount": 0,
                            "CacheWriteInputTokenCount": 0,
                            "CacheReadInputTokenCount": 0,
                        }
                    aggregated_data[date_str][metric_name] += token_count

                    # モデル別の料金で計算して集計
                    if date_str not in aggregated_costs:
                        aggregated_costs[date_str] = {
                            "InputTokenCount": 0.0,
                            "OutputTokenCount": 0.0,
                            "CacheWriteInputTokenCount": 0.0,
                            "CacheReadInputTokenCount": 0.0,
                        }
                    cost = calculate_cost(token_count, metric_name, model_id)
                    aggregated_costs[date_str][metric_name] += cost

    if not has_any_data:
        print("\nデータポイントが見つかりませんでした。")
        return

    # 日付でソート
    sorted_dates = sorted(aggregated_data.keys())

    # テーブルヘッダー
    print("=" * 126)
    print(
        f"{'Date':<12} | {'Input':<19} | {'Output':<19} | {'Cache Write':<18} | "
        f"{'Cache Read':<18} | {'Cache Ratio':<11} | {'Total'}"
    )
    print("-" * 126)

    # 総計用の変数
    grand_totals = {
        "InputTokenCount": 0,
        "OutputTokenCount": 0,
        "CacheWriteInputTokenCount": 0,
        "CacheReadInputTokenCount": 0,
    }
    grand_cost_total = 0.0

    # 日別データを出力
    for date_str in sorted_dates:
        metrics = aggregated_data[date_str]
        costs = aggregated_costs[date_str]

        # トークン数
        input_tokens = metrics["InputTokenCount"]
        output_tokens = metrics["OutputTokenCount"]
        cache_write_tokens = metrics["CacheWriteInputTokenCount"]
        cache_read_tokens = metrics["CacheReadInputTokenCount"]

        # 表示用の単位変換
        input_k = input_tokens / 1000  # k単位 (1000)
        output_k = output_tokens / 1000  # k単位 (1000)
        cache_write_m = cache_write_tokens / 1000000  # M単位 (1000000)
        cache_read_m = cache_read_tokens / 1000000  # M単位 (1000000)

        # 料金（すでにモデル別に計算済み）
        input_cost = costs["InputTokenCount"]
        output_cost = costs["OutputTokenCount"]
        cache_write_cost = costs["CacheWriteInputTokenCount"]
        cache_read_cost = costs["CacheReadInputTokenCount"]
        daily_total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

        # キャッシュ利用比率を計算
        cache_total_tokens = cache_write_tokens + cache_read_tokens
        if cache_total_tokens > 0:
            cache_ratio = (cache_read_tokens / cache_total_tokens) * 100
        else:
            cache_ratio = 0.0

        # 総計に加算
        grand_totals["InputTokenCount"] += input_tokens
        grand_totals["OutputTokenCount"] += output_tokens
        grand_totals["CacheWriteInputTokenCount"] += cache_write_tokens
        grand_totals["CacheReadInputTokenCount"] += cache_read_tokens
        grand_cost_total += daily_total_cost

        # 行を出力
        print(
            f"{date_str:<12} | "
            f"{input_k:>8,.1f}k (${input_cost:>6.2f}) | "
            f"{output_k:>8,.1f}k (${output_cost:>6.2f}) | "
            f"{cache_write_m:>7,.2f}M (${cache_write_cost:>6.2f}) | "
            f"{cache_read_m:>7,.2f}M (${cache_read_cost:>6.2f}) | "
            f"{cache_ratio:>10.1f}% | "
            f"${daily_total_cost:>10.2f}"
        )

    # 総計行を出力
    print("-" * 126)

    # 総計の単位変換
    total_input_k = grand_totals["InputTokenCount"] / 1000
    total_output_k = grand_totals["OutputTokenCount"] / 1000
    total_cache_write_m = grand_totals["CacheWriteInputTokenCount"] / 1000000
    total_cache_read_m = grand_totals["CacheReadInputTokenCount"] / 1000000

    # 総計のキャッシュ利用比率を計算
    total_cache_tokens = (
        grand_totals["CacheWriteInputTokenCount"]
        + grand_totals["CacheReadInputTokenCount"]
    )
    if total_cache_tokens > 0:
        total_cache_ratio = (
            grand_totals["CacheReadInputTokenCount"] / total_cache_tokens
        ) * 100
    else:
        total_cache_ratio = 0.0

    # 総計の料金（各メトリクスの合計料金から計算）
    total_input_cost = sum(
        aggregated_costs[date]["InputTokenCount"] for date in sorted_dates
    )
    total_output_cost = sum(
        aggregated_costs[date]["OutputTokenCount"] for date in sorted_dates
    )
    total_cache_write_cost = sum(
        aggregated_costs[date]["CacheWriteInputTokenCount"] for date in sorted_dates
    )
    total_cache_read_cost = sum(
        aggregated_costs[date]["CacheReadInputTokenCount"] for date in sorted_dates
    )

    print(
        f"{'Total':<12} | "
        f"{total_input_k:>8,.1f}k (${total_input_cost:>6.2f}) | "
        f"{total_output_k:>8,.1f}k (${total_output_cost:>6.2f}) | "
        f"{total_cache_write_m:>7,.2f}M (${total_cache_write_cost:>6.2f}) | "
        f"{total_cache_read_m:>7,.2f}M (${total_cache_read_cost:>6.2f}) | "
        f"{total_cache_ratio:>10.1f}% | "
        f"${grand_cost_total:>10.2f}"
    )
    print("=" * 126)


def main():
    """メイン処理"""
    try:
        # 設定ファイルを読み込み
        load_models_config()

        args = parse_arguments()

        # JSON出力モード以外の場合は進捗メッセージを表示
        if not args.json:
            print("メトリクス取得中...", file=sys.stderr)
            print(f"  開始日: {args.start_date}", file=sys.stderr)
            print(f"  終了日: {args.end_date}", file=sys.stderr)
            print(f"  対象モデル数: {len(MODEL_IDS)}", file=sys.stderr)
            if args.profile:
                print(f"  プロファイル: {args.profile}", file=sys.stderr)
            if args.region:
                print(f"  リージョン: {args.region}", file=sys.stderr)

        all_models_metrics = get_cloudwatch_metrics(
            args.start_date, args.end_date, args.profile, args.region, quiet=args.json
        )

        # 出力形式を選択
        if args.json:
            # JSON形式で標準出力に表示（ファイル保存なし）
            json_data = format_output_json(
                all_models_metrics, args.start_date, args.end_date
            )
            print(json.dumps(json_data, indent=2, ensure_ascii=False))
        else:
            # テーブル形式で標準出力に表示 + JSONファイルに保存
            format_output(all_models_metrics)

            # JSONデータを生成
            json_data = format_output_json(
                all_models_metrics, args.start_date, args.end_date
            )

            # デフォルトのファイルパスを生成
            if args.output is None:
                # 日付からファイル名を生成 (bedrock_claude_usage_20250912_20250913.json)
                start_compact = args.start_date.replace("-", "")
                end_compact = args.end_date.replace("-", "")
                output_file = f"bedrock_claude_usage_{start_compact}_{end_compact}.json"
            else:
                output_file = args.output

            # JSON ファイルに保存
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                print(f"\nJSONデータを保存しました: {output_file}", file=sys.stderr)
            except IOError as e:
                print(f"\nファイル保存エラー: {e}", file=sys.stderr)
                sys.exit(1)

    except ValueError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n処理が中断されました。", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
