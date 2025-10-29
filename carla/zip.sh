#!/bin/bash

# --- CARLA データセット ZIP アーカイバ (Bash版 - フラット構造対応) ---
# flatten後の構造:
#  BASE_DIR/
#    001_Town01_Opt_ClearNoon/
#       ├─ rgb_camera-front/
#       ├─ dvs_camera-front/
#       ├─ ...
#       └─ metadata-*.json
#
# 複数のシナリオを一括でZIP化します。
# センサー選択は全シナリオ共通です。

# 1. ベースディレクトリ確認
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
cd "$BASE_DIR"

# 2. シナリオ選択
echo "--- ZIP化するシナリオを選択 (複数可) ---"
all_scenarios=()
while IFS= read -r d; do
    all_scenarios+=("$(basename "$d")")
done < <(find . -maxdepth 1 -mindepth 1 -type d)

if [ ${#all_scenarios[@]} -eq 0 ]; then
    echo "エラー: シナリオディレクトリがありません。"
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
    selected_scenarios=("${all_scenarios[@]}")
else
    for choice in $choices; do
        [[ "$choice" =~ ^[0-9]+$ ]] || continue
        idx=$((choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#all_scenarios[@]} ]; then
            selected_scenarios+=("${all_scenarios[$idx]}")
        fi
    done
fi

if [ ${#selected_scenarios[@]} -eq 0 ]; then
    echo "エラー: 有効なシナリオが選択されませんでした。"
    exit 1
fi

echo "-> 対象シナリオ: ${selected_scenarios[*]}"

# 3. センサー選択（flatten: シナリオ直下）
echo ""
echo "--- ZIPに含めるデータを選択 (全シナリオ共通) ---"
FIRST_SCENARIO="${selected_scenarios[0]}"
cd "$FIRST_SCENARIO"

sensor_dirs=()
while IFS= read -r d; do
    sensor_dirs+=("$(basename "$d")")
done < <(find . -maxdepth 1 -mindepth 1 -type d)

if [ ${#sensor_dirs[@]} -eq 0 ]; then
    echo "エラー: センサディレクトリが見つかりません。"
    cd ..
    exit 1
fi

echo "  [0] ALL (全て)"
for i in "${!sensor_dirs[@]}"; do
    echo "  [$((i+1))] ${sensor_dirs[$i]}"
done
echo "---------------------------------------"

read -p "番号をスペース区切りで入力 (例: 1 3 5) (qで終了): " sensor_choices
if [[ "$sensor_choices" == "q" ]]; then
    echo "中断しました。"
    cd ..
    exit 0
fi

selected_sensors=()
if [[ "$sensor_choices" == "0" ]]; then
    selected_sensors=("${sensor_dirs[@]}")
else
    for choice in $sensor_choices; do
        [[ "$choice" =~ ^[0-9]+$ ]] || continue
        idx=$((choice - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#sensor_dirs[@]} ]; then
            selected_sensors+=("${sensor_dirs[$idx]}")
        fi
    done
fi

cd ..

echo "-> ZIP対象センサー: ${selected_sensors[*]}"
echo "-> metadata*.json も同梱します"
echo ""
echo "========================================"
echo "          ZIP処理開始
========================================"
echo ""

# 4. ZIP 実行
total=${#selected_scenarios[@]}
ok=0
ng=0

for scen in "${selected_scenarios[@]}"; do
    echo "--- 処理中: $scen ---"
    DATA_PATH="$scen"

    if [ ! -d "$DATA_PATH" ]; then
        echo "❌ ERROR: $DATA_PATH が見つかりません"
        ng=$((ng + 1))
        continue
    fi

    ZIP_FILE="$(pwd)/${scen}.zip"
    if [ -f "$ZIP_FILE" ]; then
        echo "⚠️ 既にZIPが存在 -> skip"
        ng=$((ng + 1))
        continue
    fi

    (
      cd "$DATA_PATH"
      zip -rq "$ZIP_FILE" "${selected_sensors[@]}" metadata*.json 2>/dev/null
    )
    if [ $? -eq 0 ]; then
        echo "✅ 完了: $ZIP_FILE"
        ok=$((ok + 1))
    else
        echo "❌ 失敗: $scen"
        rm -f "$ZIP_FILE"
        ng=$((ng + 1))
    fi
done

echo ""
echo "========================================"
echo "             全処理完了"
echo "========================================"
echo "  成功: $ok"
echo "  失敗/スキップ: $ng"
echo "  合計: $total"
