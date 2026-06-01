"""
========================================================================
 GLOMAP Live Monitor — Real-Time Log Watcher
========================================================================
 Run this on WINDOWS while run_glomap_all.sh executes in WSL.
 It tails all dish log files and displays color-coded live progress.

 Usage:
   python monitor_glomap.py
   python monitor_glomap.py --dish Dish_turning/Dish_1   (watch one dish)
========================================================================
"""

import os
import sys
import time
import re
import argparse
from datetime import datetime

# ── ANSI Colors ───────────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

# Assign colors to dishes
DISH_COLORS = {
    "Dish_turning/Dish_1": C.CYAN,
    "Dish_turning/Dish_2": C.GREEN,
    "Dish_turning/Dish_3": C.MAGENTA,
    "Me_walking/Dish_1":   C.YELLOW,
    "Me_walking/Dish_2":   C.BLUE,
    "Me_walking/Dish_3":   C.WHITE,
}

# Patterns to highlight
PHASE_PATTERN = re.compile(r"PHASE \d+/\d+")
DONE_PATTERN  = re.compile(r"(PHASE \d+ DONE|COMPLETE)")
ERROR_PATTERN = re.compile(r"(ERROR|FAILED|error|failed)")
METRIC_PATTERN = re.compile(r"(Registered|Points|Reproj|Mean track|observations)", re.IGNORECASE)
FEATURE_PATTERN = re.compile(r"(features|Processed file|Processing image)", re.IGNORECASE)
MATCHING_PATTERN = re.compile(r"(Matching block|Verified)", re.IGNORECASE)


def colorize_line(line, dish_label):
    """Apply syntax highlighting to a log line."""
    color = DISH_COLORS.get(dish_label, C.WHITE)
    prefix = f"{color}{C.BOLD}[{dish_label:>22s}]{C.RESET} "

    if ERROR_PATTERN.search(line):
        return prefix + f"{C.RED}{C.BOLD}{line}{C.RESET}"
    if DONE_PATTERN.search(line):
        return prefix + f"{C.GREEN}{C.BOLD}{line}{C.RESET}"
    if PHASE_PATTERN.search(line):
        return prefix + f"{C.YELLOW}{C.BOLD}{line}{C.RESET}"
    if METRIC_PATTERN.search(line):
        return prefix + f"{C.CYAN}{line}{C.RESET}"
    if FEATURE_PATTERN.search(line):
        return prefix + f"{C.DIM}{line}{C.RESET}"
    if MATCHING_PATTERN.search(line):
        return prefix + f"{C.DIM}{line}{C.RESET}"
    if "====" in line:
        return prefix + f"{C.DIM}{line}{C.RESET}"

    return prefix + line


def get_dish_status(outputs_dir, dish_label):
    """Check the current status of a dish."""
    metrics_path = os.path.join(outputs_dir, dish_label, "metrics.json")
    log_path = os.path.join(outputs_dir, dish_label, "glomap_full.log")

    if os.path.exists(metrics_path):
        return "DONE", C.GREEN
    if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
        return "RUNNING", C.YELLOW
    return "WAITING", C.DIM


def print_dashboard(outputs_dir, dishes):
    """Print a compact status dashboard."""
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{C.BOLD}{'=' * 72}{C.RESET}")
    print(f"{C.BOLD}  GLOMAP LIVE MONITOR  {C.DIM}(refreshed {now}){C.RESET}")
    print(f"{C.BOLD}{'=' * 72}{C.RESET}")

    for dish in dishes:
        status, color = get_dish_status(outputs_dir, dish)
        dish_color = DISH_COLORS.get(dish, C.WHITE)
        print(f"  {dish_color}{dish:>22s}{C.RESET}  [{color}{C.BOLD}{status:>8s}{C.RESET}]")

    print(f"{C.BOLD}{'=' * 72}{C.RESET}")
    print(f"  {C.DIM}Press Ctrl+C to stop monitoring{C.RESET}\n")


def tail_logs(outputs_dir, dishes):
    """Tail all log files simultaneously, printing new lines."""
    # Track file positions
    file_positions = {}
    for dish in dishes:
        log_path = os.path.join(outputs_dir, dish, "glomap_full.log")
        file_positions[dish] = {"path": log_path, "pos": 0, "existed": False}

    print_dashboard(outputs_dir, dishes)
    last_dashboard = time.time()
    lines_since_dashboard = 0

    while True:
        any_activity = False

        for dish in dishes:
            info = file_positions[dish]
            log_path = info["path"]

            if not os.path.exists(log_path):
                continue

            # If file just appeared, note it
            if not info["existed"]:
                info["existed"] = True
                print(colorize_line(f">> Log file detected, monitoring started", dish))

            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(info["pos"])
                    new_lines = f.readlines()
                    info["pos"] = f.tell()

                for line in new_lines:
                    line = line.rstrip()
                    if not line:
                        continue
                    print(colorize_line(line, dish))
                    lines_since_dashboard += 1
                    any_activity = True

            except (IOError, PermissionError):
                pass

        # Refresh dashboard periodically
        now = time.time()
        if now - last_dashboard > 30 and lines_since_dashboard > 20:
            print_dashboard(outputs_dir, dishes)
            last_dashboard = now
            lines_since_dashboard = 0

        # Check if all dishes are done
        all_done = all(
            os.path.exists(os.path.join(outputs_dir, d, "metrics.json"))
            for d in dishes
        )
        if all_done:
            print(f"\n{C.GREEN}{C.BOLD}  ALL DISHES COMPLETE!{C.RESET}")
            print(f"  {C.CYAN}Run: python analyze_glomap.py{C.RESET}\n")
            break

        if not any_activity:
            time.sleep(0.5)
        else:
            time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description="GLOMAP Live Monitor")
    parser.add_argument(
        "--dish", type=str, default=None,
        help="Watch a specific dish (e.g. Dish_turning/Dish_1)"
    )
    parser.add_argument(
        "--outputs_dir", type=str,
        default=r"D:\glomap_pipeline\glomap_pipeline\outputs",
        help="Path to outputs directory"
    )
    args = parser.parse_args()

    # Enable ANSI colors on Windows
    if sys.platform == "win32":
        os.system("color")

    all_dishes = [
        "Dish_turning/Dish_1", "Dish_turning/Dish_2", "Dish_turning/Dish_3",
        "Me_walking/Dish_1", "Me_walking/Dish_2", "Me_walking/Dish_3",
    ]

    if args.dish:
        if args.dish not in all_dishes:
            print(f"{C.RED}Unknown dish: {args.dish}{C.RESET}")
            print(f"Available: {', '.join(all_dishes)}")
            sys.exit(1)
        dishes = [args.dish]
    else:
        dishes = all_dishes

    print(f"\n{C.BOLD}  GLOMAP Live Monitor{C.RESET}")
    print(f"  {C.DIM}Watching: {args.outputs_dir}{C.RESET}")
    print(f"  {C.DIM}Dishes: {len(dishes)}{C.RESET}\n")

    try:
        tail_logs(args.outputs_dir, dishes)
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Monitor stopped.{C.RESET}")


if __name__ == "__main__":
    main()
