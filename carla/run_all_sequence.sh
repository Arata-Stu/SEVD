#!/bin/bash
#

# =================================================================
# 設定セクション
# =================================================================
DEFAULT_BASE_DIR="dataset"
CARLA_SCRIPT="./CarlaUE4.sh" 
SERVER_WAIT_TIME=15 
PID_FILE="/tmp/carla_server.pid" 

export NUM_EGO_VEHICLES=1
export NUM_VEHICLES=120
export NUM_WALKERS=70
export FREQUENCY_HZ=30
export IGNORE_TICKS=35
export DURATION=18000
export TIMEOUT=60

MAPS=(
    "Town01_Opt" "Town02_Opt" "Town03_Opt" "Town04_Opt"
    "Town05_Opt" "Town06_Opt" "Town07_Opt" "Town10HD_Opt"
    "Town11" "Town12" "Town13" "Town15"
)
GOOD_WEATHERS=(
    "ClearNoon" "CloudyNoon" "SoftRainNoon"
    "ClearSunset" "CloudySunset" "SoftRainSunset"
)
export DELTA_SECONDS=$(echo "scale=4; 1 / $FREQUENCY_HZ" | bc)
SIM_TIME_MIN=$(echo "scale=2; $DURATION / $FREQUENCY_HZ / 60" | bc)
NUM_MAPS=${#MAPS[@]}
NUM_WEATHERS=${#GOOD_WEATHERS[@]}
TOTAL_RUNS=$(($NUM_MAPS * $NUM_WEATHERS))

# =================================================================
# 引数解析セクション (tmux引数をパースするよう変更)
# =================================================================
START_INDEX=1
END_INDEX=$TOTAL_RUNS
BASE_DIR=$DEFAULT_BASE_DIR
SERVER_PANE="" # tmux のサーバーペインID (例: carla_data:0.0)

# getopts が解釈する引数と、このスクリプト固有の引数(--server-pane)を分離
ARGS_FOR_GETOPTS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --server-pane)
            SERVER_PANE="$2"
            shift # --server-pane
            shift # <pane_id>
            ;;
        *)
            # getopts 用の引数として保存
            ARGS_FOR_GETOPTS+=("$1")
            shift
            ;;
    esac
done

# getopts のために引数を再設定
set -- "${ARGS_FOR_GETOPTS[@]}"

usage() {
    echo "Usage: $0 (called from start_tmux.sh) [-b BASE_DIR] [-s START_INDEX] [-e END_INDEX]"
    echo "  --server-pane <pane_id> は start_tmux.sh から自動で渡されます。"
    exit 1
}

while getopts "b:s:e:h" opt; do
    case ${opt} in
        b) BASE_DIR=$OPTARG ;;
        s) START_INDEX=$OPTARG ;;
        e) END_INDEX=$OPTARG ;;
        h) usage ;;
        \?) usage ;;
    esac
done

# --server-pane が指定されていない場合はエラー
if [ -z "$SERVER_PANE" ]; then
    echo "❌ エラー: --server-pane が指定されていません。"
    echo "   このスクリプトは 'start_tmux.sh' から実行してください。"
    exit 1
fi

# =================================================================
# 実行セクション (tmux制御ロジックを追加)
# =================================================================
TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
RUN_BASE_DIR="${BASE_DIR}/${TIMESTAMP}_${START_INDEX}_${END_INDEX}"
mkdir -p "$RUN_BASE_DIR"

echo "================================================="
echo " CARLA 制御ループ (tmux) を開始します"
echo "   (このペインでAPI実行、左ペイン ($SERVER_PANE) でサーバー実行)"
echo "================================================="
echo "📂 ベースディレクトリ: $RUN_BASE_DIR"
echo "🎯 実行範囲: $START_INDEX から $END_INDEX まで"
echo "================================================="
echo ""

# 指定されたIDの範囲でループ
for (( CURRENT_RUN=START_INDEX; CURRENT_RUN<=END_INDEX; CURRENT_RUN++ ))
do
    # --- 1. パラメータの特定 ---
    IDX=$((CURRENT_RUN - 1))
    MAP_IDX=$((IDX / NUM_WEATHERS))
    WEATHER_IDX=$((IDX % NUM_WEATHERS))
    
    export MAP_NAME=${MAPS[$MAP_IDX]}
    export START_WEATHER=${GOOD_WEATHERS[$WEATHER_IDX]}
    export END_WEATHER=${GOOD_WEATHERS[$WEATHER_IDX]}
    
    RUN_ID_PADDED=$(printf "%03d" $CURRENT_RUN)
    export OUTPUT_DIR="${RUN_BASE_DIR}/${RUN_ID_PADDED}_${MAP_NAME}_${START_WEATHER}"
    mkdir -p "$OUTPUT_DIR"

    echo "================================================="
    echo "🔄 実行中 ($CURRENT_RUN/$TOTAL_RUNS)"
    echo "================================================="
    echo "   💾 保存先: $OUTPUT_DIR"
    echo ""
    
    # --- 2. Terminal 1 (左ペイン): CARLAサーバーを起動 ---
    echo "🚀 CARLAサーバーを $SERVER_PANE で起動します..."
    
    # 古いPIDファイルを削除し、サーバーをバックグラウンドで起動(&)して、
    # そのPIDをファイルに出力(>)するコマンドを tmux 経由で送信
    tmux send-keys -t "$SERVER_PANE" \
        "rm -f $PID_FILE; bash $CARLA_SCRIPT -RenderOffScreen & echo \$! > $PID_FILE" C-m

    echo "   起動待機中... ($SERVER_WAIT_TIME 秒)"
    sleep $SERVER_WAIT_TIME

    # PIDファイルが作成されたか、プロセスが実在するかを確認
    if [ ! -f "$PID_FILE" ]; then
        echo "❌ サーバーPIDファイル ($PID_FILE) が見つかりません。起動失敗。"
        tmux send-keys -t "$SERVER_PANE" "echo '!! 起動に失敗したようです !!'" C-m
        continue
    fi
    
    SERVER_PID=$(cat $PID_FILE)
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "❌ サーバー(PID: $SERVER_PID) が起動していません。スキップします。"
        tmux send-keys -t "$SERVER_PANE" "echo '!! プロセス(PID: $SERVER_PID) が見つかりません !!'" C-m
        continue
    fi
    echo "   サーバー起動完了 (PID: $SERVER_PID)"
    echo ""

    # --- 3. Terminal 2 (右ペイン): データ収集スクリプト (子) を実行 ---
    #    (環境変数は export 済みなので、そのまま呼び出す)
    bash ./run_single_carla.sh
    COLLECT_EXIT_CODE=$?

    echo ""
    if [ $COLLECT_EXIT_CODE -eq 0 ]; then
        echo "✅ データ収集 完了 ($CURRENT_RUN/$TOTAL_RUNS)"
    else
        echo "❌ データ収集 エラー ($CURRENT_RUN/$TOTAL_RUNS)"
        touch "${OUTPUT_DIR}/_ERROR"
    fi
    echo ""

    # --- 4. Terminal 1 (左ペイン): CARLAサーバーを停止 ---
    echo "🛑 CARLAサーバー (PID: $SERVER_PID) を停止します..."
    if kill -0 $SERVER_PID 2>/dev/null; then
        kill $SERVER_PID
        wait $SERVER_PID 2>/dev/null
        # 左ペインにも終了したことを通知（任意）
        tmux send-keys -t "$SERVER_PANE" "echo 'サーバー(PID: $SERVER_PID) は停止しました。'" C-m
    else
        echo "   サーバーは既に停止していました。"
    fi
    echo "   サーバー停止完了。"
    echo ""
    echo "-------------------------------------------------"
    echo ""
done

echo "================================================="
echo "✅✅ 指定範囲の全ての処理が完了しました"
echo "================================================="
# 左ペインにも完了を通知
tmux send-keys -t "$SERVER_PANE" "echo '--- 全ての処理が完了しました ---'" C-m