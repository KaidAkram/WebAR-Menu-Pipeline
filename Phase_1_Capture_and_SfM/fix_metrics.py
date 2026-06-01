import os, json, re

outputs_dir = r"d:\glomap_pipeline\glomap_pipeline\outputs"
for scenario in ["Dish_turning", "Me_walking"]:
    for dish in ["Dish_1", "Dish_2", "Dish_3"]:
        dish_dir = os.path.join(outputs_dir, scenario, dish)
        log_path = os.path.join(dish_dir, "glomap_full.log")
        metrics_path = os.path.join(dish_dir, "metrics.json")
        
        if not os.path.exists(log_path) or not os.path.exists(metrics_path):
            continue
            
        with open(log_path, "r", encoding="utf-8") as f:
            log_data = f.read()
            
        # Clean lines by removing COLMAP logging prefix
        clean_lines = [re.sub(r".*\] ", "", line) for line in log_data.split("\n")]
        clean_log = "\n".join(clean_lines)
        
        registered = re.search(r"Registered images:\s*(\d+)", clean_log, re.IGNORECASE)
        points = re.search(r"^Points:\s*(\d+)", clean_log, re.IGNORECASE | re.MULTILINE)
        observations = re.search(r"Observations:\s*(\d+)", clean_log, re.IGNORECASE)
        mean_track = re.search(r"Mean track length:\s*([\d.]+)", clean_log, re.IGNORECASE)
        mean_obs_img = re.search(r"Mean observations per image:\s*([\d.]+)", clean_log, re.IGNORECASE)
        mean_reproj = re.search(r"Mean reprojection error:\s*([\d.]+)", clean_log, re.IGNORECASE)
        
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
            
        if registered: metrics["registered_images"] = int(registered.group(1))
        if points: metrics["points_3d"] = int(points.group(1))
        if observations: metrics["observations"] = int(observations.group(1))
        if mean_track: metrics["mean_track_length"] = float(mean_track.group(1))
        if mean_obs_img: metrics["mean_observations_per_image"] = float(mean_obs_img.group(1))
        if mean_reproj: metrics["mean_reprojection_error_px"] = float(mean_reproj.group(1))
        
        if "total_images" in metrics and metrics["total_images"] > 0:
            metrics["registration_rate"] = metrics["registered_images"] / metrics["total_images"]
        
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=4)
        print(f"Fixed {scenario}/{dish}")
