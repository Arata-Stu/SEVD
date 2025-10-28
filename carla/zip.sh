#!/bin/bash

# --- CARLA データセット ZIP アーカイバ (Bash版 - 複数シーケンス対応) ---
# ベースディレクトリを実行時引数($1)から取得します。
# 複数のシナリオを一括で処理します。
# センサーの選択は全シナリオで共通です。

# エラーが発生しても続行 (個々のZIP化の失敗が他を止めないため)
# set -e をコメントアウト
# set -e

# 1. ベースディレクトリの取得 (実行時引数から)
if [ -z "$1" ]; then
    echo "エラー: ベースディレクトリが指定されていません。"
    echo "使用法: $0 /path/to/base_dir"
    exit 1
fi

BASE_DIR="$1"

if [ ! -d "$BASE_DIR" ]; then
    echo "エラー: ディレクトリ '$BASE_DIR' が見つかりません。"
    exit 1
fi

echo "ベースディレクトリ: $BASE_DIR"

# ベースディレクトリに移動 (パス解決を簡単にするため)
cd "$BASE_DIR"

# 2. シナリオディレクトリの複数選択 (./base 直下)
echo "--- ZIP化するシナリオを選択 (複数可) ---"
# findで見つかったディレクトリを配列に格納
all_scenarios=()
while IFS= read -r d; do
    all_scenarios+=("$(basename "$d")")
done < <(find . -maxdepth 1 -mindepth 1 -type d)

if [ ${#all_scenarios[@]} -eq 0 ]; then
    echo "エラー: シナリオ ディレクトリが見つかりません。"
    exit 1
fi

echo "  [0] ALL (全てのシナリオ)"
for i in "${!all_scenarios[@]}"; do
    echo "  [$((i+1))] ${all_scenarios[$i]}"
done
echo "---------------------------------------"

read -p "番号をスペース区切りで入力 (例: 1 2 5) (qで終了): " choices

if [[ "$choices" == "q" ]]; then
    echo "中断しました。"
    exit 0
fi

selected_scenarios=()
if [[ "$choices" == "0" ]]; then
    echo "-> 'ALL'が選択されました。"
    selected_scenarios=("${all_scenarios[@]}")
else
    for choice in $choices; do
        if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
            echo "警告: '$choice' は無効な番号です。スキップします。"
            continue
        fi
        idx=$((choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#all_scenarios[@]} ]; then
            selected_scenarios+=("${all_scenarios[$idx]}")
        else
            echo "警告: '$choice' は無効な番号です。スキップします。"
        fi
    done
fi

if [ ${#selected_scenarios[@]} -eq 0 ]; then
    echo "エラー: 有効なシナリオが選択されませんでした。"
    exit 1
fi

echo "-> 以下のシナリオを処理します: ${selected_scenarios[*]}"

# 3. センサーディレクトリの共通選択
#    (最初に見つかったシナリオのego0を代表として使用)
echo ""
echo "--- ZIPに含めるデータを選択 (全シーケンス共通) ---"

# 代表となるセンサーリストを取得
FIRST_SCENARIO="${selected_scenarios[0]}"
FIRST_SEQUENCE=$(find "$FIRST_SCENARIO" -maxdepth 1 -mindepth 1 -type d | head -n 1)
FIRST_EGO0="$FIRST_SEQUENCE/ego0"

if [ ! -d "$FIRST_EGO0" ]; then
    echo "エラー: 代表センサーリストの取得に失敗しました。"
    echo "       '$FIRST_EGO0' が見つかりません。"
    exit 1
fi

cd "$FIRST_EGO0"
sensor_dirs=()
while IFS= read -r d; do
    sensor_dirs+=("$(basename "$d")")
done < <(find . -maxdepth 1 -mindepth 1 -type d)

if [ ${#sensor_dirs[@]} -eq 0 ]; then
    echo "エラー: センサーディレクトリが見つかりません。"
    cd ../../.. # BASE_DIRに戻る
    exit 1
fi

echo "  [0] ALL (全てのデータ)"
for i in "${!sensor_dirs[@]}"; do
    echo "  [$((i+1))] ${sensor_dirs[$i]}"
done
echo "---------------------------------------"

read -p "番号をスペース区切りで入力 (例: 1 2 5) (qで終了): " sensor_choices

if [[ "$sensor_choices" == "q" ]]; then
    echo "中断しました。"
    cd ../../.. # BASE_DIRに戻る
    exit 0
fi

selected_sensors=()
if [[ "$sensor_choices" == "0" ]]; then
    echo "-> 'ALL'が選択されました。"
    selected_sensors=("${sensor_dirs[@]}")
else
    for choice in $sensor_choices; do
        if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
            echo "警告: '$choice' は無効な番号です。スキップします。"
            continue
        fi
        idx=$((choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#sensor_dirs[@]} ]; then
            selected_sensors+=("${sensor_dirs[$idx]}")
        else
            echo "警告: '$choice' は無効な番号です。スキップします。"
        fi
    done
fi

if [ ${#selected_sensors[@]} -eq 0 ]; then
    echo "エラー: 有効なデータが選択されませんでした。"
    cd ../../.. # BASE_DIRに戻る
    exit 1
fi

# BASE_DIRに戻る
cd ../../..

echo "-> 以下のセンサーをZIPします: ${selected_sensors[*]}"
echo ""
echo "========================================"
echo "          ZIP処理を開始します"
echo "========================================"
echo ""

# 4. 選択された全シナリオをループ処理
total_count=${#selected_scenarios[@]}
success_count=0
fail_count=0

for i in "${!selected_scenarios[@]}"; do
    scenario="${selected_scenarios[$i]}"
    echo "--- 処理中 ($((i+1))/$total_count): $scenario ---"

    # (A) シーケンスの自動検出
    sequence_dirs=()
    while IFS= read -r d; do
        sequence_dirs+=("$d") # パスごと (例: 001_Town.../Town01_Opt...)
    done < <(find "$scenario" -maxdepth 1 -mindepth 1 -type d)

    if [ ${#sequence_dirs[@]} -ne 1 ]; then
        echo "❌ エラー: '$scenario' 内のシーケンス検出に失敗 (0個または複数)。スキップします。"
        fail_count=$((fail_count + 1))
        continue
    fi
    sequence_path="${sequence_dirs[0]}" # (例: 001_Town.../Town01_Opt...)
    
    # (B) ego0 パスの確定
    DATA_PATH="$sequence_path/ego0"
    if [ ! -d "$DATA_PATH" ]; then
        echo "❌ エラー: データフォルダ '$DATA_PATH' が見つかりません。スキップします。"
        fail_count=$((fail_count + 1))
        continue
    fi

    # (C) ZIPファイル名の決定
    ZIP_FILENAME="${scenario}.zip"
    ZIP_FILE_PATH="$(pwd)/$ZIP_FILENAME" # $BASE_DIRのフルパス

    echo "  出力ファイル: $ZIP_FILE_PATH"

    if [ -f "$ZIP_FILE_PATH" ]; then
        # 既存ファイルは自動的にスキップ (上書き確認を省略)
        echo "⚠️ 警告: ファイルが既に存在するため、スキップします。"
        fail_count=$((fail_count + 1))
        continue
    fi

    # (D) ZIP実行
    # サブシェルで実行し、パスをクリーンにする
    (
        cd "$DATA_PATH"
        # -r: 再帰的に, -q: 静かに
        zip -rq "$ZIP_FILE_PATH" "${selected_sensors[@]}"
    )

    if [ $? -eq 0 ]; then
        echo "✅ 成功: $scenario"
        success_count=$((success_count + 1))
    else
        echo "❌ エラー: $scenario のZIP化に失敗しました。"
        rm -f "$ZIP_FILE_PATH" # 失敗したZIPファイルを削除
        fail_count=$((fail_count + 1))
    fi
    echo "----------------------------------------"
done

echo ""
echo "========================================"
echo "            全処理が完了しました"
echo "========================================"
echo "  成功: $success_count"
echo "  失敗/スキップ: $fail_count"
echo "  合計: $total_count"