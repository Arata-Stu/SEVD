#!/bin/bash

# =================================================================
# 設定セクション
# =================================================================

# ループで実行したいマップのリスト
# ここに実行したいマップ名を追加・削除してください
MAPS=(
    "Town01_Opt"
    "Town02_Opt"
    "Town03_Opt"
    "Town04_Opt"
    "Town05_Opt"
    "Town06_Opt"
    "Town07_Opt"
    "Town10HD_Opt"
    "Town11"
    "Town12"
    "Town13"
    "Town15"
)

# ループで実行したい天候のリスト
# ユーザー提供のリストに基づいています。ここに追加・削除してください
WEATHERS=(
    "ClearNoon"
    "CloudyNoon"
    "WetNoon"
    "WetCloudyNoon"
    "MidRainyNoon"
    "HardRainNoon"
    "SoftRainNoon"
    "ClearSunset"
    "CloudySunset"
    "WetSunset"
    "WetCloudySunset"
    "MidRainSunset"
    "HardRainSunset"
    "SoftRainSunset"
    "ClearNight"
    "CloudyNight"
    "WetNight"
    "WetCloudyNight"
    "SoftRainNight"
    "MidRainyNight"
    "HardRainNight"
    "DustStorm"
    "FoggyNoon"
    "FoggySunset"
    "FoggyNight"
)

# -----------------------------------------------------------------
# 固定パラメータ (これらの値はループ全体で共通です)
# -----------------------------------------------------------------

# Ego車両の数
NUM_EGO_VEHICLES=1

# 他車両(NPC)の数
NUM_VEHICLES=120

# 歩行者(NPC)の数
NUM_WALKERS=70

# 動作周波数(Hz)。この値からdelta-secondsが自動計算されます。
FREQUENCY_HZ=30

# シミュレーション開始後にデータ収集を無視するフレーム数
IGNORE_TICKS=35

# データ収集を行う総フレーム数 (シミュレーション時間[秒] = DURATION / FREQUENCY_HZ)
DURATION=18000

# CARLAサーバーへの接続タイムアウト(秒)
TIMEOUT=60

# =================================================================
# 実行セクション
# =================================================================

# 動作周波数(Hz)からdelta-secondsを計算 (浮動小数点計算のためbcを使用)
DELTA_SECONDS=$(echo "scale=4; 1 / $FREQUENCY_HZ" | bc)

# 収集時間を計算
SIM_TIME_SEC=$(echo "$DURATION / $FREQUENCY_HZ" | bc)
SIM_TIME_MIN=$(echo "scale=2; $SIM_TIME_SEC / 60" | bc)

# 総実行回数の計算
TOTAL_MAPS=${#MAPS[@]}
TOTAL_WEATHERS=${#WEATHERS[@]}
TOTAL_RUNS=$((TOTAL_MAPS * TOTAL_WEATHERS))
CURRENT_RUN=0

echo "================================================="
echo " CARLAデータ生成ループを開始します"
echo "================================================="
echo "🗺️  対象マップ数: $TOTAL_MAPS"
echo "☀️🌙 対象天候数: $TOTAL_WEATHERS"
echo "🔄  総実行回数: $TOTAL_RUNS 回"
echo "================================================="
echo ""

# マップと天候の組み合わせでループ実行
for map_name in "${MAPS[@]}"; do
    for weather_name in "${WEATHERS[@]}"; do

        CURRENT_RUN=$((CURRENT_RUN + 1))

        # 実行前の設定確認
        echo "-------------------------------------------------"
        echo "🔄 実行中 ($CURRENT_RUN/$TOTAL_RUNS)"
        echo "-------------------------------------------------"
        echo "🗺️  マップ: $map_name"
        echo "☀️  天候: $weather_name"
        echo "🚗  交通量: 車両 $NUM_VEHICLES 台, 歩行者 $NUM_WALKERS 人"
        echo "⏱️  動作周波数: $FREQUENCY_HZ Hz (delta-seconds: $DELTA_SECONDS)"
        echo "⏳  シミュレーション時間: $DURATION フレーム (約 $SIM_TIME_MIN 分)"
        echo "-------------------------------------------------"
        echo ""

        # main.py の実行
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
            # エラーが発生した場合、ここでスクリプトを終了させることも可能です
            # exit 1
        fi
        echo ""

    done
done

echo "================================================="
echo "✅✅ 全てのデータ生成が完了しました"
echo "================================================="