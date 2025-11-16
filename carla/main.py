import traceback
import sys
import subprocess
import glob
import shutil
import os
import concurrent.futures
from datetime import datetime
import time
from tqdm import tqdm

try:
    sys.path.append(glob.glob('./carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
    print(glob.glob('./carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64')))
except IndexError:
    pass

import carla
from carla import Transform, Location, Rotation
import argparse
import logging
from npc_spawning import spawnWalkers, spawnVehicles
from configuration import attachSensorsToVehicle, SimulationParams, setupTrafficManager, setupWorld, setupWorldWeather, createOutputDirectories, CarlaSyncMode
import save_sensors
import random
import json
import queue
from os import path
from ego_vehicle import EgoVehicle
from fixed_perception import FixedPerception
from utils.arg_parser import CommandLineArgsParser
from utils.weather import weather_presets


def main():

    args_parser = CommandLineArgsParser()
    args = args_parser.parse_args()
    print(args)

    # Create CARLA client
    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)

    # Setup simulation parameters
    SimulationParams.town_map = args.map
    SimulationParams.num_of_walkers = args.number_of_walkers
    SimulationParams.num_of_vehicles = args.number_of_vehicles
    SimulationParams.delta_seconds = args.delta_seconds
    SimulationParams.ignore_first_n_ticks = args.ignore_first_n_ticks
    SimulationParams.number_of_ego_vehicles = args.number_of_ego_vehicles
    SimulationParams.PHASE = SimulationParams.town_map + "_" + SimulationParams.dt_string
    SimulationParams.data_output_subfolder = os.path.join(args.output_dir, SimulationParams.PHASE)
    SimulationParams.manual_control = args.manual_control
    SimulationParams.fixed_perception = args.fixed_perception
    SimulationParams.res = args.res
    SimulationParams.autopilot = args.autopilot
    SimulationParams.debug = args.debug
    SimulationParams.start_weather = args.start_weather
    SimulationParams.end_weather = args.end_weather
    SimulationParams.duration = args.duration

    # Load world
    world = client.load_world(SimulationParams.town_map)
    world = client.get_world()

    # Remove all parked vehicles etc.
    def disable_env(label):
        objs = world.get_environment_objects(label)
        for o in objs:
            world.enable_environment_objects({o.id}, False)

    disable_env(carla.CityObjectLabel.Car)
    disable_env(carla.CityObjectLabel.Bicycle)
    disable_env(carla.CityObjectLabel.Bus)
    disable_env(carla.CityObjectLabel.Motorcycle)
    disable_env(carla.CityObjectLabel.Pedestrians)
    disable_env(carla.CityObjectLabel.Train)
    disable_env(carla.CityObjectLabel.Truck)

    # Setup world
    setupWorld(world)
    setupTrafficManager(client)

    # Load all blueprints
    blueprint_library = world.get_blueprint_library()
    blueprintsVehicles = blueprint_library.filter('vehicle.*')
    vehicles_spawn_points = world.get_map().get_spawn_points()
    blueprintsWalkers = blueprint_library.filter('walker.pedestrian.*')
    walker_controller_bp = blueprint_library.find('controller.ai.walker')
    lidar_segment_bp = blueprint_library.find('sensor.lidar.ray_cast_semantic')

    participant_density = {
        'bicycle': 0,
        'truck': 0,
        'van': 0,
        'car': 0,
        'motorcycle': 0,
        'pedestrian': 0
    }

    # ============================================================
    # 🚀 車種ごとのスポーン制限：ここだけ追加すればOK
    # ============================================================

    total = SimulationParams.num_of_vehicles

    max_vehicle_types = {
        "car": int(total * 0.6),
        "van": int(total * 0.1),
        "truck": int(total * 0.1),
        "motorcycle": int(total * 0.2),
        "bicycle": 0, ## 0
    }
    
    filtered_vehicle_bps = []
    for bp in blueprintsVehicles:
        if bp.has_attribute("base_type"):
            t = bp.get_attribute("base_type").as_string()
            if t in max_vehicle_types and max_vehicle_types[t] > 0:
                filtered_vehicle_bps.append(bp)

    print(f"Filtered vehicle blueprints: {len(filtered_vehicle_bps)} / {len(blueprintsVehicles)}")

    # Walker は必要ならフィルタ可能（今回は全使用）
    filtered_walker_bps = blueprintsWalkers

    # ============================================================
    # 🚀 spawn（フィルタ済み blueprint を使う）
    # ============================================================
    w_all_actors, w_all_id = spawnWalkers(
        client, world, filtered_walker_bps, SimulationParams.num_of_walkers
    )

    for actor in w_all_actors:
        if actor.attributes["role_name"] == "pedestrian":
            participant_density["pedestrian"] += 1
    world.tick()

    egos = []
    fixed = []
    map_name = world.get_map().name

    # Fixed sensors
    if SimulationParams.fixed_perception:
        with open(SimulationParams.fixed_perception_sensor_locations_json_filepath, 'r') as json_file:
            sensor_locations = json.load(json_file)
        SimulationParams.town_map = map_name.split("/")[-1]
        for config_entry in sensor_locations:
            if config_entry["town"] == map_name:
                for coordinate in config_entry["cordinates"]:
                    fixed.append(FixedPerception(
                        SimulationParams.fixed_perception_sensor_json_filepath, None, world, args, coordinate))

    # Ego vehicles
    for i in range(SimulationParams.number_of_ego_vehicles):
        egos.append(EgoVehicle(SimulationParams.sensor_json_filepath, None, world, args))

    # ============================================================
    # 🚀 車両 spawn（フィルタ済み vehicle blueprints 使用）
    # ============================================================
    v_all_actors, v_all_id = spawnVehicles(
        client, world, vehicles_spawn_points,
        filtered_vehicle_bps,                     # ← ここが本体
        SimulationParams.num_of_vehicles
    )

    for actor in v_all_actors:
        actor_type = actor.attributes.get('base_type')
        if actor_type in participant_density:
            participant_density[actor_type] += 1

    world.tick()

    print("Starting simulation...")

    # ------------------------------
    # Processing functions
    # ------------------------------

    def process_egos(i, frame_id):
        data = egos[i].getSensorData(frame_id)
        output_folder = os.path.join(SimulationParams.data_output_subfolder, "ego" + str(i))
        try:
            save_sensors.saveAllSensors(output_folder, data, egos[i].sensor_names, world)
            control = egos[i].ego.get_control()
            angle = control.steer
            save_sensors.saveSteeringAngle(angle, output_folder)
        except Exception:
            traceback.print_exc()

    def process_fixed(i, frame_id):
        data = fixed[i].getSensorData(frame_id)
        output_folder = os.path.join(SimulationParams.data_output_subfolder, "fixed-" + str(i+1))
        try:
            save_sensors.saveAllSensors(output_folder, data, fixed[i].sensor_names, world)
        except Exception:
            traceback.print_exc()

    # ------------------------------
    # Weather interpolation
    # ------------------------------

    def interpolate_weather(start_weather, end_weather, progress):
        return carla.WeatherParameters(
            cloudiness=start_weather.cloudiness + (end_weather.cloudiness - start_weather.cloudiness) * progress,
            dust_storm=start_weather.dust_storm + (end_weather.dust_storm - start_weather.dust_storm) * progress,
            fog_density=start_weather.fog_density + (end_weather.fog_density - start_weather.fog_density) * progress,
            fog_distance=start_weather.fog_distance + (end_weather.fog_distance - start_weather.fog_distance) * progress,
            fog_falloff=start_weather.fog_falloff + (end_weather.fog_falloff - start_weather.fog_falloff) * progress,
            mie_scattering_scale=start_weather.mie_scattering_scale,
            precipitation=start_weather.precipitation + (end_weather.precipitation - start_weather.precipitation) * progress,
            precipitation_deposits=start_weather.precipitation_deposits + (end_weather.precipitation_deposits - start_weather.precipitation_deposits) * progress,
            rayleigh_scattering_scale=start_weather.rayleigh_scattering_scale,
            scattering_intensity=start_weather.scattering_intensity + (end_weather.scattering_intensity - start_weather.scattering_intensity) * progress,
            sun_azimuth_angle=start_weather.sun_azimuth_angle + (end_weather.sun_azimuth_angle - start_weather.sun_azimuth_angle) * progress,
            sun_altitude_angle=start_weather.sun_altitude_angle + (end_weather.sun_altitude_angle - start_weather.sun_altitude_angle) * progress,
            wind_intensity=start_weather.wind_intensity + (end_weather.wind_intensity - start_weather.wind_intensity) * progress,
            wetness=start_weather.wetness + (end_weather.wetness - start_weather.wetness) * progress,
        )

    # ------------------------------
    # Metadata save
    # ------------------------------

    start_weather = None
    end_weather = None
    for name, value in weather_presets:
        if name == SimulationParams.start_weather:
            start_weather = value
        if name == SimulationParams.end_weather:
            end_weather = value

    if (start_weather is None) or (end_weather is None):
        raise ValueError("Invalid weather preset name provided.")

    world.set_weather(start_weather)

    metadata = {
        "start_weather": SimulationParams.start_weather,
        "end_weather": SimulationParams.end_weather,
        "duration": SimulationParams.duration,
        "map_name": map_name,
        "participant_density": participant_density,
        "delta_seconds": SimulationParams.delta_seconds,
        "egos": len(egos),
        "fixed-views": len(fixed)
    }

    json_string = json.dumps(metadata, indent=4)
    file_path = f'{SimulationParams.data_output_subfolder}/metadata-{datetime.now().strftime("%Y%m%d%H%M%S")}.json'
    with open(file_path, "w") as file:
        file.write(json_string)

    # ------------------------------
    # Simulation loop
    # ------------------------------

    try:
        with CarlaSyncMode(world, []) as sync_mode:

            print("Ignoring initial frames...")
            for _ in range(SimulationParams.ignore_first_n_ticks):
                sync_mode.tick(timeout=5.0)

            print("Starting data collection...")
            for step in tqdm(range(1, SimulationParams.duration + 1), desc="Data Collection"):
                frame_id = sync_mode.tick(timeout=5.0)

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(process_egos, i, frame_id) for i in range(len(egos))]
                    concurrent.futures.wait(futures)

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(process_fixed, i, frame_id) for i in range(len(fixed))]
                    concurrent.futures.wait(futures)

                progress = step / SimulationParams.duration
                current_weather = interpolate_weather(start_weather, end_weather, progress)
                world.set_weather(current_weather)

    finally:
        print("\nSimulation finished. Starting cleanup...")

        print("Stopping walkers...")
        for actor in w_all_actors:
            try:
                if actor.is_alive:
                    actor.stop()
            except Exception:
                pass

        print("Destroying all actors...")
        client.apply_batch([carla.command.DestroyActor(x) for x in w_all_id])
        client.apply_batch([carla.command.DestroyActor(x) for x in v_all_id])

        for ego in egos:
            ego.destroy()

        print("Ticking world to finalize cleanup...")
        try:
            for _ in range(5):
                world.tick()
        except RuntimeError:
            pass

        print("Disabling synchronous mode...")
        settings = world.get_settings()
        if settings.synchronous_mode:
            settings.synchronous_mode = False
            settings.fixed_delta_seconds = None
            world.apply_settings(settings)

        print("Cleanup completed.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript interrupted by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        traceback.print_exc()

