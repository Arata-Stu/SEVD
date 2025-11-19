import carla
from carla import command
import random
import time

# Aliases
SpawnActor = carla.command.SpawnActor
SetAutopilot = carla.command.SetAutopilot
FutureActor = carla.command.FutureActor

# ============================================================
# 🚗 Vehicle Spawning
# ============================================================

def spawnVehicles(client, world, spawn_points, blueprint_library, ratios, total_num):

    # --- CATEGORIES_IDS はそのまま ---
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

            # # ---------------------------
            # # 🚌 Bus（1種）
            # # ---------------------------
            # "bus": [
            #     "vehicle.mitsubishi.fusorosa",
            # ],

            # ---------------------------
            # 🚲 Bicycle（3種）
            # ---------------------------
            # "bicycle": [
            #     "vehicle.bh.crossbike",
            #     "vehicle.diamondback.century",
            #     "vehicle.gazelle.omafiets",
            # ],
        }


    # 1) 実在 blueprint でフィルタ
    CATEGORIES = {}
    for cat, ids in CATEGORIES_IDS.items():
        valid_bps = []
        for bp_id in ids:
            try:
                valid_bps.append(blueprint_library.find(bp_id))
            except IndexError:
                print(f"[WARN] Blueprint {bp_id} not found.")
        CATEGORIES[cat] = valid_bps

    # 2) spawn_plan 作成
    spawn_plan = {cat: int(total_num * ratio) for cat, ratio in ratios.items()}
    diff = total_num - sum(spawn_plan.values())
    if diff > 0:
        valid = [c for c in ratios if len(CATEGORIES[c]) > 0]
        if valid:
            biggest = max(valid, key=lambda c: ratios[c])
            spawn_plan[biggest] += diff

    print("[Spawn Plan]", spawn_plan)

    # 3) 1台ずつスポーン + retry
    all_ids = []
    all_actors = []

    MAX_RETRY = 10

    for category, num in spawn_plan.items():
        bps = CATEGORIES.get(category, [])
        if num == 0 or len(bps) == 0:
            continue

        for i in range(num):
            bp = random.choice(bps)

            success = False
            for retry in range(MAX_RETRY):
                sp = random.choice(spawn_points)

                # ---- ここが重要：1 spawn ごとに apply_batch_sync ----
                result = client.apply_batch_sync(
                    [command.SpawnActor(bp, sp).then(
                        command.SetAutopilot(command.FutureActor, True)
                    )],
                    True
                )[0]

                if result.error:
                    print(f"[WARN] spawn failed retry={retry+1}/{MAX_RETRY} : {result.error}")
                    time.sleep(0.05)
                    continue
                else:
                    actor_id = result.actor_id
                    all_ids.append(actor_id)
                    all_actors.append(world.get_actor(actor_id))
                    print(f"[OK] Spawned {bp.id} id={actor_id}")
                    success = True
                    break

            if not success:
                print(f"[ERROR] Could not spawn {bp.id} after {MAX_RETRY} retries")

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
