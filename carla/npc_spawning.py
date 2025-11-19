import carla
from carla import command
import random

# Aliases
SpawnActor = carla.command.SpawnActor
SetAutopilot = carla.command.SetAutopilot
FutureActor = carla.command.FutureActor


# ============================================================
# 🚗 Vehicle Spawning
# ============================================================
def spawnVehicles(client, world, spawn_points, blueprint_library, ratios, total_num):
    """
    NPC 車両を、カテゴリー比率に基づいてスポーンする。

    Args:
        client: carla.Client
        world: carla.World
        spawn_points: list of Transform
        blueprint_library: world.get_blueprint_library()
        ratios: dict (car / van / truck / motorcycle / bus / bicycle)
        total_num: int (総スポーン数)
    """

    # ----------------------------------------------------
    # Blueprint 一覧（あなたのCARLA環境で確認済み）
    # ----------------------------------------------------
    CATEGORIES_IDS = {
        # ---------------------------
        # 🚗 Car（23種）
        # ---------------------------
        "car": [
            "vehicle.audi.a2",
            "vehicle.mercedes.coupe_2020",
            "vehicle.chevrolet.impala",
            "vehicle.citroen.c3",
            "vehicle.micro.microlino",
            "vehicle.audi.tt",
            "vehicle.jeep.wrangler_rubicon",
            "vehicle.mini.cooper_s",
            "vehicle.mercedes.coupe",
            "vehicle.dodge.charger_2020",
            "vehicle.lincoln.mkz_2020",
            "vehicle.mini.cooper_s_2021",
            "vehicle.ford.crown",
            "vehicle.toyota.prius",
            "vehicle.audi.etron",
            "vehicle.seat.leon",
            "vehicle.ford.mustang",
            "vehicle.lincoln.mkz_2017",
            "vehicle.nissan.micra",
            "vehicle.nissan.patrol",
            "vehicle.nissan.patrol_2021",
            "vehicle.bmw.grandtourer",
            "vehicle.tesla.model3",
            "vehicle.dodge.charger_police",
            "vehicle.dodge.charger_police_2020",
        ],

        # ---------------------------
        # 🚐 Van（4種）
        # ---------------------------
        "van": [
            "vehicle.ford.ambulance",
            "vehicle.mercedes.sprinter",
            "vehicle.volkswagen.t2_2021",
            "vehicle.volkswagen.t2",
        ],

        # ---------------------------
        # 🚛 Truck（4種）
        # ---------------------------
        "truck": [
            "vehicle.carlamotors.european_hgv",
            "vehicle.carlamotors.carlacola",
            "vehicle.carlamotors.firetruck",
            "vehicle.tesla.cybertruck",
        ],

        # ---------------------------
        # 🏍 Motorcycle（4種）
        # ---------------------------
        "motorcycle": [
            "vehicle.kawasaki.ninja",
            "vehicle.yamaha.yzf",
            "vehicle.harley-davidson.low_rider",
            "vehicle.vespa.zx125",
        ],

        # ---------------------------
        # 🚌 Bus（1種）
        # ---------------------------
        "bus": [
            "vehicle.mitsubishi.fusorosa",
        ],

        # ---------------------------
        # 🚲 Bicycle（3種）
        # ---------------------------
        "bicycle": [
            "vehicle.bh.crossbike",
            "vehicle.diamondback.century",
            "vehicle.gazelle.omafiets",
        ],
    }

    # ----------------------------------------------------
    # 1) Blueprint 存在確認
    # ----------------------------------------------------
    CATEGORIES = {}
    for cat, ids in CATEGORIES_IDS.items():
        valid_bps = []
        for bp_id in ids:
            try:
                bp = blueprint_library.find(bp_id)
                valid_bps.append(bp)
            except IndexError:
                print(f"[WARN] Blueprint not found: {bp_id}")

        if not valid_bps:
            print(f"[WARN] No blueprints available for category: {cat}")

        CATEGORIES[cat] = valid_bps

    # ----------------------------------------------------
    # 2) 割合から spawn_plan を作る
    # ----------------------------------------------------
    spawn_plan = {}
    for cat, ratio in ratios.items():
        spawn_plan[cat] = int(total_num * ratio)

    # 合計ズレ補正
    diff = total_num - sum(spawn_plan.values())
    if diff > 0:
        valid_ratio_items = [(cat, r) for cat, r in ratios.items() if CATEGORIES[cat]]
        if valid_ratio_items:
            max_cat = max(valid_ratio_items, key=lambda x: x[1])[0]
            spawn_plan[max_cat] += diff

    print("[INFO] Spawn plan (before cleanup):", spawn_plan)

    # ----------------------------------------------------
    # 3) Blueprint が無いカテゴリは 0 に矯正
    # ----------------------------------------------------
    removed = 0
    for cat in list(spawn_plan.keys()):
        if len(CATEGORIES[cat]) == 0:
            removed += spawn_plan[cat]
            spawn_plan[cat] = 0

    if removed > 0:
        valid = [cat for cat in spawn_plan if len(CATEGORIES[cat]) > 0]
        if valid:
            spawn_plan[valid[0]] += removed

    print("[INFO] Spawn plan (final):", spawn_plan)

    # ----------------------------------------------------
    # 4) batch 作成
    # ----------------------------------------------------
    batch = []
    spawn_log = []

    for cat, num in spawn_plan.items():
        if num == 0 or not CATEGORIES[cat]:
            continue

        for _ in range(num):
            bp = random.choice(CATEGORIES[cat])
            sp = random.choice(spawn_points)
            spawn_log.append(bp.id)

            batch.append(
                command.SpawnActor(bp, sp).then(
                    command.SetAutopilot(command.FutureActor, True)
                )
            )

    if not batch:
        print("[WARN] No vehicles to spawn (batch empty).")
        return [], []

    # ----------------------------------------------------
    # 5) 実際にスポーン
    # ----------------------------------------------------
    results = client.apply_batch_sync(batch, True)

    all_ids = []
    for i, r in enumerate(results):
        if r.error:
            print(f"[ERROR] Spawn failed: {spawn_log[i]} -> {r.error}")
        else:
            print(f"[SPAWN] {spawn_log[i]}  -> id={r.actor_id}")
            all_ids.append(r.actor_id)

    all_actors = world.get_actors(all_ids)

    print(f"[INFO] Vehicles spawned successfully: {len(all_actors)} / {len(spawn_log)}")

    return all_actors, all_ids


# ============================================================
# 🚶 Walker Spawning
# ============================================================
def spawnWalkers(client, world, blueprintsWalkers, number):
    print("Spawning walkers...")

    # 1. ランダム地点生成
    spawn_points = []
    for _ in range(number):
        sp = carla.Transform()
        sp.location = world.get_random_location_from_navigation()
        if sp.location:
            spawn_points.append(sp)

    # 2. 歩行者本体の spawn
    batch = []
    for sp in spawn_points:
        walker_bp = random.choice(blueprintsWalkers)
        batch.append(SpawnActor(walker_bp, sp))

    results = client.apply_batch_sync(batch, True)

    walkers = [{"id": r.actor_id} for r in results]

    # 3. AI controller の spawn
    walker_controller_bp = world.get_blueprint_library().find('controller.ai.walker')
    batch = []
    for w in walkers:
        batch.append(SpawnActor(walker_controller_bp, carla.Transform(), w["id"]))

    con_results = client.apply_batch_sync(batch, True)
    for i, r in enumerate(con_results):
        walkers[i]["con"] = r.actor_id

    all_ids = []
    for w in walkers:
        all_ids.append(w["con"])
        all_ids.append(w["id"])

    all_actors = world.get_actors(all_ids)

    # 4. AI 起動
    world.tick()
    for i in range(0, len(all_actors), 2):
        con = all_actors[i]
        con.start()
        con.go_to_location(world.get_random_location_from_navigation())
        con.set_max_speed(1 + random.random())

    return all_actors, all_ids
