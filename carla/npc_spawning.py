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
    安全なスポーン：衝突で spawn 失敗した場合はリトライする。
    """

    # ===========================
    # 1. blueprint 準備（前と同じ）
    # ===========================
    
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



    # Blueprint 存在チェック
    CATEGORIES = {}
    for cat, ids in CATEGORIES_IDS.items():
        valid = []
        for bp_id in ids:
            try:
                bp = blueprint_library.find(bp_id)
                valid.append(bp)
            except IndexError:
                print(f"[WARN] Missing blueprint: {bp_id}")
        CATEGORIES[cat] = valid

    # ===========================
    # 2. spawn_plan 作成
    # ===========================
    spawn_plan = {cat: int(total_num * ratio) for cat, ratio in ratios.items()}
    diff = total_num - sum(spawn_plan.values())
    if diff > 0:
        largest = max(ratios, key=lambda c: ratios[c])
        spawn_plan[largest] += diff

    print("[Spawn plan]", spawn_plan)

    # ===========================
    # 3. spawn retry ロジック
    # ===========================
    final_ids = []
    max_attempts = 20   # 1台あたり retry 回数

    for category, count in spawn_plan.items():
        bps = CATEGORIES[category]
        if not bps or count == 0:
            continue

        print(f"\n[SPAWN] Category = {category}, Target = {count}")

        for i in range(count):
            success = False
            for attempt in range(max_attempts):
                bp = random.choice(bps)
                sp = random.choice(spawn_points)

                result = client.apply_batch_sync([
                    command.SpawnActor(bp, sp)
                        .then(command.SetAutopilot(command.FutureActor, True))
                ], True)[0]

                if result.error:
                    # 衝突によるエラーが多い
                    print(f"[RETRY] {bp.id} failed ({result.error}) attempt={attempt+1}")
                    continue

                # 成功！
                print(f"[OK] Spawned {bp.id} id={result.actor_id}")
                final_ids.append(result.actor_id)
                success = True
                break

            if not success:
                print(f"[FAIL] Could NOT spawn vehicle in category {category}")

    # ===========================
    # 4. gather actors
    # ===========================
    final_actors = world.get_actors(final_ids)

    print(f"\n[SUMMARY] Spawned vehicles = {len(final_ids)} / {total_num}")

    return final_actors, final_ids



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
