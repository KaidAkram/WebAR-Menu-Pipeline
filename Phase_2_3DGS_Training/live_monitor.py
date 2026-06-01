import os
import time
import glob
import re
import matplotlib.pyplot as plt

# Configure PhD-level aesthetics using pure matplotlib
plt.style.use('ggplot')
plt.rcParams.update({
    "figure.figsize": (10, 6),
    "axes.titlesize": 16,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "lines.linewidth": 2.5,
    "lines.markersize": 6,
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"]
})

BASE_DIR = r"D:\3DGS\gaussian-splatting\output\glomap_v2"

def parse_log(filepath):
    data = {
        'iter_loss': [], 'loss': [],
        'iter_fps': [], 'fps': [],
        'iter_heavy': [], 'psnr_test': [], 'psnr_train': [],
        'ssim': [], 'lpips': [], 'model_size': []
    }
    
    current_heavy_iter = None
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
    for line in lines:
        # Fast Metrics
        if "Iter:" in line and "Loss:" in line:
            try:
                parts = line.strip().split('|')
                it = int(parts[0].replace("Iter:", "").strip())
                loss = float(parts[1].replace("Loss:", "").strip())
                fps = float(parts[2].replace("FPS:", "").strip())
                
                data['iter_loss'].append(it)
                data['loss'].append(loss)
                data['iter_fps'].append(it)
                data['fps'].append(fps)
            except Exception:
                pass
                
        # Heavy Metrics Header
        elif "--- HEAVY METRICS [Iter" in line:
            try:
                match = re.search(r"Iter (\d+)", line)
                if match:
                    current_heavy_iter = int(match.group(1))
            except Exception:
                pass
                
        # Test Set Metrics
        elif "Test  Set:" in line and current_heavy_iter is not None:
            try:
                # Test  Set: L1 0.05000 | PSNR 22.50 | SSIM 0.85000 | LPIPS 0.15000
                psnr = float(re.search(r"PSNR ([\d\.]+)", line).group(1))
                ssim = float(re.search(r"SSIM ([\d\.]+)", line).group(1))
                lpips = float(re.search(r"LPIPS ([\d\.]+)", line).group(1))
                
                data['iter_heavy'].append(current_heavy_iter)
                data['psnr_test'].append(psnr)
                data['ssim'].append(ssim)
                data['lpips'].append(lpips)
            except Exception:
                pass
                
        # Train Set Metrics
        elif "Train Set:" in line and current_heavy_iter is not None:
            try:
                # Train Set: L1 0.04000 | PSNR 23.50
                psnr = float(re.search(r"PSNR ([\d\.]+)", line).group(1))
                # Ensure it aligns with the last iter_heavy
                if len(data['psnr_train']) < len(data['iter_heavy']):
                     data['psnr_train'].append(psnr)
            except Exception:
                pass
                
        # Model Size
        elif "Model Size:" in line and current_heavy_iter is not None:
            try:
                size = float(re.search(r"Model Size: ([\d\.]+)", line).group(1))
                if len(data['model_size']) < len(data['iter_heavy']):
                    data['model_size'].append(size)
                # Reset current heavy iter to avoid bleeding
                current_heavy_iter = None
            except Exception:
                pass

    return data

def render_charts(data, output_dir, dish_name):
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Loss Curve
    if data['iter_loss']:
        plt.figure()
        plt.plot(data['iter_loss'], data['loss'], color='#e74c3c')
        plt.title(f"{dish_name}: Optimization Stability (Loss)")
        plt.xlabel("Iterations")
        plt.ylabel("L1 + D-SSIM Loss")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "01_loss_curve.png"), dpi=300)
        plt.close()
        
    # 2. PSNR Curve
    if data['iter_heavy'] and data['psnr_test']:
        plt.figure()
        plt.plot(data['iter_heavy'], data['psnr_test'], label="Test Set PSNR", marker='o', color='#3498db')
        if len(data['psnr_train']) == len(data['iter_heavy']):
            plt.plot(data['iter_heavy'], data['psnr_train'], label="Train Set PSNR", marker='x', linestyle='--', color='#2ecc71')
        plt.axhline(y=28.0, color='r', linestyle=':', label='Production Target (>28dB)')
        plt.title(f"{dish_name}: Signal-to-Noise Ratio (PSNR)")
        plt.xlabel("Iterations")
        plt.ylabel("PSNR (dB)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "02_psnr_curve.png"), dpi=300)
        plt.close()

    # 3. SSIM Curve
    if data['iter_heavy'] and data['ssim']:
        plt.figure()
        plt.plot(data['iter_heavy'], data['ssim'], marker='s', color='#9b59b6')
        plt.axhline(y=0.85, color='r', linestyle=':', label='Production Target (>0.85)')
        plt.title(f"{dish_name}: Structural Similarity (SSIM)")
        plt.xlabel("Iterations")
        plt.ylabel("SSIM Index")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "03_ssim_curve.png"), dpi=300)
        plt.close()

    # 4. LPIPS Curve
    if data['iter_heavy'] and data['lpips']:
        plt.figure()
        plt.plot(data['iter_heavy'], data['lpips'], marker='d', color='#e67e22')
        plt.axhline(y=0.10, color='r', linestyle=':', label='Production Target (<0.10)')
        plt.title(f"{dish_name}: Perceptual Fidelity (LPIPS)")
        plt.xlabel("Iterations")
        plt.ylabel("VGG LPIPS Distance (Lower is better)")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "04_lpips_curve.png"), dpi=300)
        plt.close()

    # 5. FPS Curve
    if data['iter_fps']:
        plt.figure()
        # Smooth FPS slightly to avoid massive spikes
        if len(data['fps']) > 10:
            smoothed_fps = np.convolve(data['fps'], np.ones(10)/10, mode='valid')
            x_smoothed = data['iter_fps'][9:]
            plt.plot(x_smoothed, smoothed_fps, color='#1abc9c')
        else:
            plt.plot(data['iter_fps'], data['fps'], color='#1abc9c')
        plt.title(f"{dish_name}: Hardware Throughput (FPS)")
        plt.xlabel("Iterations")
        plt.ylabel("Frames Per Second")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "05_fps_curve.png"), dpi=300)
        plt.close()

    # 6. Model Size Curve
    if data['iter_heavy'] and data['model_size']:
        plt.figure()
        plt.plot(data['iter_heavy'], data['model_size'], marker='^', color='#34495e')
        plt.title(f"{dish_name}: Storage Footprint (Model Size)")
        plt.xlabel("Iterations")
        plt.ylabel("Megabytes (MB)")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "06_model_size_curve.png"), dpi=300)
        plt.close()

def main():
    print("==================================================")
    print("PhD-Level 3DGS Live Monitoring Service Started")
    print("==================================================")
    print(f"Watching directory: {BASE_DIR}")
    
    try:
        import numpy as np
    except ImportError:
        print("CRITICAL: numpy is required. Please install it.")
        return

    while True:
        log_files = glob.glob(os.path.join(BASE_DIR, "**", "live_monitoring.txt"), recursive=True)
        
        for log_file in log_files:
            # e.g. D:\3DGS\gaussian-splatting\output\glomap_v2\Dish_turning\Dish_1\live_monitoring.txt
            dish_dir = os.path.dirname(log_file)
            dish_name = os.path.basename(dish_dir)
            strategy_name = os.path.basename(os.path.dirname(dish_dir))
            full_dish_name = f"{strategy_name} / {dish_name}"
            
            viz_dir = os.path.join(dish_dir, "visualizations")
            
            try:
                data = parse_log(log_file)
                render_charts(data, viz_dir, full_dish_name)
                print(f"[{time.ctime()}] Updated 6 charts for {full_dish_name}")
            except Exception as e:
                print(f"Error parsing {log_file}: {e}")
                
        # Sleep for 60 seconds before re-scanning
        time.sleep(60)

if __name__ == "__main__":
    main()
