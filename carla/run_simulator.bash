#!/bin/bash
# 使用するマップ名 (例: Town01, Town03, Town05, Town10HD_Opt)
MAP_NAME="Town10HD_Opt"

# Ego車両の数
NUM_EGO_VEHICLES=1

# 他車両(NPC)の数
NUM_VEHICLES=120

# 歩行者(NPC)の数
NUM_WALKERS=70

# 動作周波数(Hz)。この値からdelta-secondsが自動計算されます。
FREQUENCY_HZ=10

# シミュレーション開始後にデータ収集を無視するフレーム数
IGNORE_TICKS=35

# データ収集を行う総フレーム数 (シミュレーション時間[秒] = DURATION / FREQUENCY_HZ)
DURATION=9000

# 開始時の天候 (例: ClearNoon, CloudySunset, HardRainNight, FoggyNoon)
START_WEATHER="ClearNoon"

# 終了時の天候 (開始と同じにすると天候は変化しません)
END_WEATHER="ClearNight"

# CARLAサーバーへの接続タイムアウト(秒)
TIMEOUT=60

-----------------------------------------

# 動作周波数(Hz)からdelta-secondsを計算 (浮動小数点計算のためbcを使用)
DELTA_SECONDS=$(echo "scale=4; 1 / $FREQUENCY_HZ" | bc)

# 収集時間を計算して表示
SIM_TIME_SEC=$(echo "$DURATION / $FREQUENCY_HZ" | bc)
SIM_TIME_MIN=$(echo "scale=2; $SIM_TIME_SEC / 60" | bc)

# 実行前の設定確認
echo "================================================="
echo " CARLAデータ生成を開始します"
echo "================================================="
echo "🗺️  マップ: $MAP_NAME"
echo "🚗  交通量: 車両 $NUM_VEHICLES 台, 歩行者 $NUM_WALKERS 人"
echo "⏱️  動作周波数: $FREQUENCY_HZ Hz (delta-seconds: $DELTA_SECONDS)"
echo "⏳  シミュレーション時間: $DURATION フレーム (約 $SIM_TIME_MIN 分)"
echo "☀️🌙 天候: $START_WEATHER -> $END_WEATHER"
echo "================================================="
echo ""

# main.py の実行
python main.py \
    --map=$MAP_NAME \
    --number-of-ego-vehicles=$NUM_EGO_VEHICLES \
    -n=$NUM_VEHICLES \
    -w=$NUM_WALKERS \
    --sync \
    --delta-seconds=$DELTA_SECONDS \
    --timeout=$TIMEOUT \
    --ignore-first-n-ticks=$IGNORE_TICKS \
    --duration=$DURATION \
    --start-weather=$START_WEATHER \
    --end-weather=$END_WEATHER \
    -a

EXIT_CODE=$?

echo ""
echo "================================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ スクリプトの実行が正常に完了しました"
else
    echo "❌ スクリプトの実行中にエラーが発生しました (終了コード: $EXIT_CODE)"
fi
echo "================================================="