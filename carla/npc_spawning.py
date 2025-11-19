import carla
from carla import command
import random
import logging
import math

# @todo cannot import these directly.
SpawnActor = carla.command.SpawnActor
SetAutopilot = carla.command.SetAutopilot
SetVehicleLightState = carla.command.SetVehicleLightState
FutureActor = carla.command.FutureActor


def spawnVehicles(client, world, spawn_points, blueprint_library, ratios, total_num):
    """
    ratios = {
        "car": 0.60,
        "van": 0.10,
        "truck": 0.10,
        "motorcycle": 0.20,
        "bus": 0.00,
        "bicycle": 0.00,
    }
    """

    # カテゴリ別の blueprint ID 候補
    CATEGORIES_IDS = {
        "car": [
            "vehicle.dodge.charger_2020",
            "vehicle.dodge.charger_police_2020",
            "vehicle.ford.crown_taxi",   # ← ここが無い環境もある
            "vehicle.lincoln.mkz_2020",
            "vehicle.mercedes.coupe_2020",
            "vehicle.mini.cooper_s_2021",
            "vehicle.nissan.patrol_2021",
        ],
        "van": [
            "vehicle.ford.ambulance",
            "vehicle.mercedes.sprinter",
            "vehicle.volkswagen.t2_2021",
        ],
        "truck": [
            "vehicle.carlamotors.european_hgv",
            "vehicle.carlamotors.firetruck",
            "vehicle.tesla.cybertruck",
        ],
        "motorcycle": [
            "vehicle.harley-davidson.low_rider",
            "vehicle.kawasaki.ninja",
            "vehicle.vespa.zx125",
            "vehicle.yamaha.yzf",
        ],
        "bus": [
            "vehicle.mitsubishi.fusorosa",
        ],
        "bicycle": [
            "vehicle.bh.crossbike",
            "vehicle.diamondback.century",
            "vehicle.gazelle.omafiets",
        ],
    }

    # ----------------------------------------------------
    # 1) 実際に存在する Blueprint だけにフィルタリング
    # ----------------------------------------------------
    CATEGORIES = {}
    for cat, ids in CATEGORIES_IDS.items():
        bps = []
        for bp_id in ids:
            try:
                bp = blueprint_library.find(bp_id)
            except IndexError:
                print(f"[WARN] Blueprint '{bp_id}' not found. Skipping.")
                continue
            bps.append(bp)

        if not bps:
            print(f"[WARN] No valid blueprints found for category '{cat}'.")
        CATEGORIES[cat] = bps

    # ----------------------------------------------------
    # 2) 割合から spawn_plan を作成
    # ----------------------------------------------------
    spawn_plan = {}
    for cat, ratio in ratios.items():
        spawn_plan[cat] = int(total_num * ratio)

    # 合計を total_num に合わせて補正
    diff = total_num - sum(spawn_plan.values())
    if diff > 0:
        # 一番比率の高いカテゴリに余りを足す（存在しないカテゴリは除外）
        valid_ratio_items = [
            (cat, r) for cat, r in ratios.items() if CATEGORIES.get(cat)
        ]
        if valid_ratio_items:
            max_cat = max(valid_ratio_items, key=lambda x: x[1])[0]
            spawn_plan[max_cat] += diff

    print("Spawn plan (before invalid-category fix) =", spawn_plan)

    # Blueprint が1つもないカテゴリは 0 にする
    removed = 0
    for cat, num in list(spawn_plan.items()):
        if not CATEGORIES.get(cat):
            removed += num
            spawn_plan[cat] = 0

    # もし削られたぶんがあれば、有効なカテゴリに追加
    if removed > 0:
        valid_cats = [c for c in spawn_plan.keys() if CATEGORIES.get(c)]
        if valid_cats:
            # とりあえず最初の有効カテゴリに寄せる
            spawn_plan[valid_cats[0]] += removed

    print("Spawn plan (final) =", spawn_plan)

    # ----------------------------------------------------
    # 3) batch command 生成
    # ----------------------------------------------------
    batch = []

    for category, num in spawn_plan.items():
        bps = CATEGORIES.get(category, [])
        if num == 0 or not bps:
            continue

        for _ in range(num):
            bp = random.choice(bps)
            sp = random.choice(spawn_points)
            batch.append(
                command.SpawnActor(bp, sp).then(
                    command.SetAutopilot(command.FutureActor, True)
                )
            )

    # ----------------------------------------------------
    # 4) Spawn 実行
    # ----------------------------------------------------
    if not batch:
        print("[WARN] Vehicle spawn batch is empty. No vehicles will be spawned.")
        return [], []

    results = client.apply_batch_sync(batch, True)
    all_id = [results[i].actor_id for i in range(len(results)) if results[i].error is None]
    all_actors = world.get_actors(all_id)
    return all_actors, all_id



def spawnWalkers(client, world, blueprintsWalkers, number):
    print("Spawning walkers...")

    # 1. Take all the random locations to spawn
    spawn_points = []
    for i in range(number):
        spawn_point = carla.Transform()
        spawn_point.location = world.get_random_location_from_navigation()
        if (spawn_point.location != None):
            spawn_points.append(spawn_point)

    # 2. Build the batch of commands to spawn the pedestrians
    batch = []
    for spawn_point in spawn_points:
        walker_bp = random.choice(blueprintsWalkers)
        batch.append(carla.command.SpawnActor(walker_bp, spawn_point))

    # 2.1 apply the batch
    results = client.apply_batch_sync(batch, True)
    walkers_list = []
    for i in range(len(results)):
        walkers_list.append({"id": results[i].actor_id})

    # 3. Spawn walker AI controllers for each walker
    batch = []
    walker_controller_bp = world.get_blueprint_library().find('controller.ai.walker')

    for i in range(len(walkers_list)):
        batch.append(
            carla.command.SpawnActor(
                walker_controller_bp,
                carla.Transform(),
                walkers_list[i]["id"]
            )
        )

    # 3.1 apply the batch
    results = client.apply_batch_sync(batch, True)
    for i in range(len(results)):
        walkers_list[i]["con"] = results[i].actor_id

    # 4. Put altogether the walker and controller ids
    all_id = []
    for i in range(len(walkers_list)):
        all_id.append(walkers_list[i]["con"])
        all_id.append(walkers_list[i]["id"])
    all_actors = world.get_actors(all_id)

    # wait for a tick
    world.tick()

    # 5. initialize walker AI
    for i in range(0, len(all_actors), 2):
        all_actors[i].start()
        all_actors[i].go_to_location(world.get_random_location_from_navigation())
        all_actors[i].set_max_speed(1 + random.random())

    return all_actors, all_id
