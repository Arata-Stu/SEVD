import numpy as np
import glob
import os
from pathlib import Path
import argparse
import re
import hashlib
from tqdm import tqdm  

def get_frame_number(filepath):
    filename = os.path.basename(filepath)
    matches = re.findall(r'(\d+)', filename)
    if matches:
        return int(matches[-1])
    return -1

def check_events(dvs_dir, width, height):
    print("--- 1. イベント (DVS) データの検証 ---")
    
    npz_files = sorted(
        glob.glob(os.path.join(dvs_dir, 'dvs-*-xytp.npz')),
        key=get_frame_number
    )
    
    if not npz_files:
        print("❌ エラー: DVS NPZファイルが見つかりません。")
        print(f"   (検索パス: {dvs_dir})")
        return None, None, set()

    print(f"✅ NPZファイル数: {len(npz_files)}")

    t_start = 0
    t_end = 0

    try:
        first_file_path = npz_files[0]
        last_file_path = npz_files[-1]

        with np.load(first_file_path) as data_first:
            events_first = data_first['dvs_events']
            if events_first.size == 0:
                print(f"⚠️ 警告: 最初のNPZファイル {first_file_path} が空です。")
                t_start = 0
            else:
                t_start = events_first['t'].min()
                
        with np.load(last_file_path) as data_last:
            events_last = data_last['dvs_events']
            if events_last.size == 0:
                print(f"⚠️ 警告: 最後のNPZファイル {last_file_path} が空です。")
                t_end = 0
            else:
                t_end = events_last['t'].max()

        if t_start == 0 and t_end == 0 and len(npz_files) > 1:
             print("❌ エラー: イベントファイルが空のため、期間を計算できません。")
             return None, None, set()
        elif t_start == 0 and t_end == 0 and len(npz_files) == 1:
             print("⚠️ 警告: 唯一のイベントファイルが空です。")
             return None, None, set()

        duration_sec = (t_end - t_start) / 1_000_000_000
        print(f"✅ 期間 (Duration): {duration_sec:.2f} 秒 (目標: 600秒)")
        print(f"   - 開始時刻 (ns): {t_start}")
        print(f"   - 終了時刻 (ns): {t_end}")

    except Exception as e:
        print(f"❌ エラー: NPZファイルの読み込みに失敗しました。 {e}")
        return None, None, set()

    try:
        with np.load(first_file_path) as data:
            if 'dvs_events' not in data:
                print("❌ エラー: NPZに 'dvs_events' キーがありません。")
                return None, None, set()
            
            events = data['dvs_events']
            
            expected_dtype_fields = [('x', '<u2'), ('y', '<u2'), ('t', '<i8'), ('pol', '?')]
            print(f"✅ データ型 (dtype): {events.dtype}")

            if list(events.dtype.names) != ['x', 'y', 't', 'pol']:
                 print(f"   ⚠️ 警告: 期待されるdtypeフィールド名 ['x', 'y', 't', 'pol'] と異なります。")

            if events.size > 0:
                x_max, y_max = events['x'].max(), events['y'].max()
                print(f"✅ 値の範囲: x_max={x_max} (幅={width}), y_max={y_max} (高さ={height})")
                if x_max >= width or y_max >= height:
                    print(f"   ❌ エラー: イベント座標がセンサーサイズ ({width}x{height}) を超えています。")
            
            pol_values = np.unique(events['pol'])
            print(f"✅ 極性 (pol) の値: {pol_values}")
            if events.size > 0 and not np.all(np.isin(pol_values, [True, False])):
                print(f"   ❌ エラー: 極性値が [True, False] 以外を含んでいます。")

    except Exception as e:
        print(f"❌ エラー: 最初のNPZファイルの詳細チェックに失敗しました。 {e}")
        return None, None, set()

    if len(npz_files) > 1:
        try:
            with np.load(npz_files[0]) as data_0:
                if data_0['dvs_events'].size > 0:
                    t_max_0 = data_0['dvs_events']['t'].max()
                else:
                    t_max_0 = 0
            
            with np.load(npz_files[1]) as data_1:
                if data_1['dvs_events'].size > 0:
                    t_min_1 = data_1['dvs_events']['t'].min()
                else:
                    t_min_1 = t_max_0
            
            print(f"✅ タイムスタンプ単調増加 (ファイル間):")
            print(f"   - F0 max(t): {t_max_0}")
            print(f"   - F1 min(t): {t_min_1}")
            if t_max_0 > t_min_1:
                print(f"   ❌ エラー: タイムスタンプが単調増加していません！ (F0のmax > F1のmin)")
        except Exception as e:
            print(f"⚠️ 警告: 単調増加チェック中にエラー。 {e}")
            
    frame_numbers = set(get_frame_number(f) for f in npz_files)
    return t_start, t_end, frame_numbers


def check_bboxes(dvs_dir, rgb_dir):
    print("\n--- 2. BBox (TXT) データの検証 ---")
    
    txt_files_dvs = sorted(
        glob.glob(os.path.join(dvs_dir, '*.txt')),
        key=get_frame_number
    )
    txt_files_rgb = sorted(
        glob.glob(os.path.join(rgb_dir, '*.txt')),
        key=get_frame_number
    )
    
    if not txt_files_rgb:
        print("❌ エラー: [rgb_camera-front] に BBox TXTファイルが見つかりません。")
        print(f"   (検索パス: {rgb_dir})")
        return set()

    if not txt_files_dvs:
        print("❌ エラー: [dvs_camera-front] に BBox TXTファイルが見つかりません。")
        print(f"   (検索パス: {dvs_dir})")
        return set()

    print(f"✅ TXTファイル数 (RGB): {len(txt_files_rgb)}")
    print(f"✅ TXTファイル数 (DVS): {len(txt_files_dvs)}")

    frames_rgb = {get_frame_number(f): f for f in txt_files_rgb}
    frames_dvs = {get_frame_number(f): f for f in txt_files_dvs}

    if set(frames_rgb.keys()) == set(frames_dvs.keys()):
        print("✅ BBoxファイル名 (RGB vs DVS): 同期しています。")
    else:
        print("❌ エラー: BBoxファイル名 (RGB vs DVS): 同期ズレがあります。")
        if set(frames_rgb.keys()) - set(frames_dvs.keys()):
            print(f"   - DVSに存在しないRGB BBoxフレーム: {len(set(frames_rgb.keys()) - set(frames_dvs.keys()))}個")
        if set(frames_dvs.keys()) - set(frames_rgb.keys()):
            print(f"   - RGBに存在しないDVS BBoxフレーム: {len(set(frames_dvs.keys()) - set(frames_rgb.keys()))}個")
    
    common_frames = set(frames_rgb.keys()) & set(frames_dvs.keys())
    if not common_frames:
        print("❌ エラー: 共通のBBoxフレームが1つもありません。内容比較をスキップします。")
        return set(frames_rgb.keys())

    try:
        first_file_path = txt_files_rgb[0]
        with open(first_file_path, 'r') as f:
            first_line = f.readline().strip()
        
        if not first_line:
            print(f"⚠️ 警告: 最初のTXTファイル {first_file_path} が空です（BBoxが0個）。")
        else:
            parts = first_line.split()
            print(f"✅ Kitti形式チェック (最初の行):")
            print(f"   - クラス名: {parts[0]}")
            print(f"   - 分割数: {len(parts)} (期待値: 15 or 16)")
            if len(parts) != 15 and len(parts) != 16:
                print(f"   ❌ エラー: Kitti 3D形式 (15列) または互換形式ではありません。")
                
    except Exception as e:
        print(f"❌ エラー: TXTファイルの読み込みまたはパースに失敗しました。 {e}")
        return set(frames_rgb.keys())

    print("✅ BBoxファイル内容 (RGB vs DVS) の比較を開始...")
    mismatch_found = False
    
    def get_file_hash(filepath):
        sha256 = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    sha256.update(data)
            return sha256.hexdigest()
        except Exception as e:
            print(f"   ❌ ハッシュ計算エラー: {filepath} ({e})")
            return None

    for frame in sorted(list(common_frames)):
        if frame == -1: continue

        file_rgb = frames_rgb[frame]
        file_dvs = frames_dvs[frame]
        
        hash_rgb = get_file_hash(file_rgb)
        hash_dvs = get_file_hash(file_dvs)

        if hash_rgb is None or hash_dvs is None:
            mismatch_found = True
            if not mismatch_found:
                 print(f"   ❌ エラー: {frame}.txt のハッシュ計算に失敗しました。")
        elif hash_rgb != hash_dvs:
            mismatch_found = True
            if not mismatch_found:
                print(f"   ❌ エラー: {frame}.txt ({os.path.basename(file_rgb)}) の内容が一致しません。")

    if not mismatch_found:
        print("✅ BBoxファイル内容 (RGB vs DVS): 全ての共通ファイルが完全に一致しました。")
    else:
        print("❌ エラー: BBoxファイル内容 (RGB vs DVS): 一致しないファイルが見つかりました。")

    return set(frames_rgb.keys())

def check_optical_flow(flow_dir, fps, width, height):
    print("\n--- 3. Optical Flow (NPZ) データの検証 ---")
    
    npz_files = sorted(
        glob.glob(os.path.join(flow_dir, '*.npz')),
        key=get_frame_number
    )
    
    if not npz_files:
        print("❌ エラー: Optical Flow NPZファイルが見つかりません。")
        print(f"   (検索パス: {flow_dir})")
        return set()

    file_count = len(npz_files)
    duration_sec = file_count / fps
    print(f"✅ ファイル数: {file_count}")
    print(f"✅ 期間 (推定): {duration_sec:.2f} 秒 ( = {file_count}F / {fps}fps )")
    
    try:
        with np.load(npz_files[0]) as data:
            if 'flow' not in data:
                print("❌ エラー: NPZに 'flow' キーがありません。")
                return set()
            
            flow_data = data['flow']
            print(f"✅ データ構造: 'flow' キーを発見")
            
            expected_shape = (height, width, 2)
            print(f"✅ データ形状 (Shape): {flow_data.shape} (期待値: {expected_shape})")
            if flow_data.shape != expected_shape:
                print(f"   ❌ エラー: データ形状が期待値と異なります。")

    except Exception as e:
        print(f"❌ エラー: Flow NPZファイルの読み込みに失敗しました。 {e}")
        return set()
        
    frame_numbers = set(get_frame_number(f) for f in npz_files)
    return frame_numbers


def check_synchronization(events_frames, bboxes_frames, flow_frames):
    print("\n--- 4. センサー間同期 (フレーム番号) の検証 ---")
    
    if events_frames == bboxes_frames:
        print("✅ BBox (RGB) vs Events (NPZ): 同期しています。")
    else:
        print("⚠️ BBox (RGB) vs Events (NPZ): 同期ズレがあります。")
        if bboxes_frames - events_frames:
            print(f"   - Events(NPZ)に存在しないBBox(TXT)フレーム: {len(bboxes_frames - events_frames)}個")
        if events_frames - bboxes_frames:
            print(f"   - BBox(TXT)に存在しないEvents(NPZ)フレーム: {len(events_frames - bboxes_frames)}個")
            
    if events_frames == flow_frames:
        print("✅ Flow (NPZ) vs Events (NPZ): 同期しています。")
    else:
        print("⚠️ Flow (NPZ) vs Events (NPZ): 同期ズレがあります。")
        if flow_frames - events_frames:
            print(f"   - Events(NPZ)に存在しないFlow(NPZ)フレーム: {len(flow_frames - events_frames)}個")
        if events_frames - flow_frames:
            print(f"   - Flow(NPZ)に存在しないEvents(NPZ)フレーム: {len(events_frames - flow_frames)}個")
    
    if bboxes_frames == flow_frames:
        print("✅ BBox (RGB) vs Flow (NPZ): 同期しています。")
    else:
        print("⚠️ BBox (RGB) vs Flow (NPZ): 同期ズレがあります。")
        if flow_frames - bboxes_frames:
            print(f"   - BBox(TXT)に存在しないFlow(NPZ)フレーム: {len(flow_frames - bboxes_frames)}個")
        if bboxes_frames - flow_frames:
            print(f"   - Flow(NPZ)に存在しないBBox(TXT)フレーム: {len(bboxes_frames - flow_frames)}個")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CARLA生データ検証スクリプト (H5/NPY変換前)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "data_root", 
        type=str, 
        help="検証したいベースディレクトリ (例: ./<base>/) や、特定のシーケンス/Egoディレクトリ (例: .../sequence_1/ego0/)"
    )
    parser.add_argument(
        "--height", 
        type=int, 
        required=True, 
        help="センサーの高さ (例: 720)"
    )
    parser.add_argument(
        "--width", 
        type=int, 
        required=True, 
        help="センサーの幅 (例: 1280)"
    )
    parser.add_argument(
        "--fps", 
        type=float, 
        required=True, 
        help="Optical Flowの記録FPS (例: 10.0)"
    )
    
    args = parser.parse_args()

    data_root_path = Path(args.data_root)
    
    sequence_paths_to_check = []
    
    DVS_DIR_NAME = "dvs_camera-front"
    RGB_DIR_NAME = "rgb_camera-front"
    FLOW_DIR_NAME = "optical_flow-front"

    is_ego_dir = data_root_path.name == "ego0" and (data_root_path / DVS_DIR_NAME).is_dir()
    is_sequence_dir = (data_root_path / "ego0" / DVS_DIR_NAME).is_dir()

    if is_ego_dir:
        sequence_paths_to_check.append(data_root_path)
        print(f"--- 単一シーケンスモード (Ego指定): {data_root_path.parent.name}/{data_root_path.name} ---")

    elif is_sequence_dir:
        sequence_paths_to_check.append(data_root_path / "ego0")
        print(f"--- 単一シーケンスモード (Sequence指定): {data_root_path.name}/ego0 ---")

    else:
        print(f"--- 複数シーケンスモード (ベースパス: {data_root_path}) ---")
        
        found_ego_dirs = sorted(list(data_root_path.glob('**/ego0')))
        
        sequence_paths_to_check = [
            ego_path for ego_path in found_ego_dirs 
            if (ego_path / DVS_DIR_NAME).is_dir()
        ]

        if not sequence_paths_to_check:
            print(f"❌ エラー: ベースディレクトリ {data_root_path} 以下に有効な 'ego0' ディレクトリ（{DVS_DIR_NAME} を含む）が見つかりません。")
            print("   検索パス例: .../<senario_X>/<sequence_Y>/ego0/")
            exit()
            
        print(f"🔍 発見した対象シーケンス ({len(sequence_paths_to_check)}件):")
        for p in sequence_paths_to_check:
            try:
                print(f"  - {p.relative_to(data_root_path)}")
            except ValueError:
                print(f"  - {p}")

    all_checks_passed = True
    
    # 👈 tqdm でループをラップ
    for seq_path in tqdm(sequence_paths_to_check, desc="シーケンス検証", unit="seq"):
        print(f"\n=============================================")
        
        try:
            relative_name = seq_path.relative_to(data_root_path.parent if (is_ego_dir or is_sequence_dir) else data_root_path)
        except ValueError:
            relative_name = seq_path 
            
        print(f"=== 📊 検証開始: {relative_name}")
        print(f"=============================================")

        dvs_dir = seq_path / DVS_DIR_NAME
        rgb_dir = seq_path / RGB_DIR_NAME
        flow_dir = seq_path / FLOW_DIR_NAME
        
        if not (dvs_dir.is_dir() and rgb_dir.is_dir() and flow_dir.is_dir()):
            print(f"❌ エラー: {seq_path} に必要なサブディレクトリ ({DVS_DIR_NAME}, {RGB_DIR_NAME}, {FLOW_DIR_NAME}) が揃っていません。")
            print(f"   dvs: {dvs_dir.is_dir()}, rgb: {rgb_dir.is_dir()}, flow: {flow_dir.is_dir()}")
            print(f"=== ⏭️  {seq_path} をスキップします ===")
            all_checks_passed = False
            continue

        t_start, t_end, events_frames = check_events(dvs_dir, args.width, args.height)
        bboxes_frames = check_bboxes(dvs_dir, rgb_dir) 
        flow_frames = check_optical_flow(flow_dir, args.fps, args.width, args.height)
        
        if events_frames and bboxes_frames and flow_frames:
            check_synchronization(events_frames, bboxes_frames, flow_frames)
        
        print(f"=== ✅ {relative_name} の検証完了 ===")

    print("\n--- 全ての検証が完了しました ---")