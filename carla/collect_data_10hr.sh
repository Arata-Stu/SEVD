#!/bin/bash

# =================================================================
# 設定セクション
# =================================================================

MAPS=(
    "Town01_Opt" "Town02_Opt" "Town03_Opt" "Town04_Opt" 
    "Town05_Opt" "Town06_Opt" "Town07_Opt" "Town10HD_Opt" 
    "Town11" "Town12" "Town13" "Town15"
)
GOOD_WEATHERS=(
    "ClearNoon" "CloudyNoon" "SoftRainNoon" 
    "ClearSunset" "CloudySunset" "SoftRainSunset"
)


NUM_EGO_VEHICLES=1
NUM_VEHICLES=120
NUM_WALKERS=70
FREQUENCY_HZ=30
IGNORE_TICKS=35
DURATION=18000 
TIMEOUT=60

# =================================================================
# 引数解析セクション
# =================================================================
TOTAL_RUNS=$((${#MAPS[@]} * ${#GOOD_WEATHERS[@]}))

# デフォルトの実行範囲（最初から最後まで）
START_INDEX=1
END_INDEX=$TOTAL_RUNS

# ヘルプメッセージ
usage() {
    echo "Usage: $0 [-s START_INDEX] [-e END_INDEX]"
    echo "  -s  開始インデックス (デフォルト: 1)"
    echo "  -e  終了インデックス (デフォルト: $TOTAL_RUNS)"
    exit 1
}

# コマンドラインオプションを解析
while getopts "s:e:h" opt; do
    case ${opt} in
        s) START_INDEX=$OPTARG ;;
        e) END_INDEX=$OPTARG ;;
        h) usage ;;
        \?) usage ;;
    esac
done

# =================================================================
# 実行セクション
# =================================================================

DELTA_SECONDS=$(echo "scale=4; 1 / $FREQUENCY_HZ" | bc)
SIM_TIME_MIN=$(echo "scale=2; $DURATION / $FREQUENCY_HZ / 60" | bc)

CURRENT_RUN=0

echo "================================================="
echo " CARLAデータ生成ループを開始します"
echo "================================================="
echo "🔄 総実行回数: $TOTAL_RUNS 回"
echo "🎯 今回の実行範囲: $START_INDEX から $END_INDEX まで"
echo "================================================="
echo ""

# 全てのマップと天候の組み合わせでループ
for map_name in "${MAPS[@]}"; do
    for weather_name in "${GOOD_WEATHERS[@]}"; do
        CURRENT_RUN=$((CURRENT_RUN + 1))

        # 現在の実行回数が指定範囲内かチェック
        if (( CURRENT_RUN >= START_INDEX && CURRENT_RUN <= END_INDEX )); then
            
            echo "-------------------------------------------------"
            echo "🔄 実行中 ($CURRENT_RUN/$TOTAL_RUNS)"
            echo "-------------------------------------------------"
            echo "🗺️  マップ: $map_name"
            echo "☀️  天候: $weather_name"
            echo "⏳  シミュレーション時間: 約 $SIM_TIME_MIN 分"
            echo "-------------------------------------------------"
            echo ""

            python main.py \
                --map="$map_name" \
                --start-weather="$weather_name" \
                --end-weather="$weather_name" \
                --number-of-ego-vehicles=$NUM_EGO_VEHICLES \
                -n=$NUM_VEHICLES \
                -w=$NUM_WALKERS \
                --sync \
                --delta-seconds=$DELTA_SECONDS \
                --timeout=$TIMEOUT \
                --ignore-first-n-ticks=$IGNORE_TICKS \
                --duration=$DURATION \
                -a

            EXIT_CODE=$?

            echo ""
            if [ $EXIT_CODE -eq 0 ]; then
                echo "✅ 完了: $map_name / $weather_name"
            else
                echo "❌ エラー発生: $map_name / $weather_name (終了コード: $EXIT_CODE)"
            fi
            echo ""

        else
            # 実行範囲外の場合はスキップメッセージを表示
            echo "⏭️  スキップ ($CURRENT_RUN/$TOTAL_RUNS): $map_name / $weather_name"
        fi
    done
done

echo "================================================="
echo "✅✅ 指定範囲の処理が完了しました"
echo "================================================="