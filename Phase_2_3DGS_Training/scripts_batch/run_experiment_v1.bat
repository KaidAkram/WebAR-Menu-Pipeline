@echo off
cd /d "%~dp0\.."
setlocal enabledelayedexpansion

echo ==========================================
echo REPRODUCING PHD EXPERIMENT V1 (Hedgehog Overfitting)
echo ==========================================

set CONDA_PATH=C:\anaconda3
call "%CONDA_PATH%\Scripts\activate.bat" gaussian_splatting

set DISH_DIR=D:\glomap_pipeline\glomap_pipeline\processed_data\Dish_turning\Dish_1
set OUT_DIR=D:\3DGS\gaussian-splatting\output\glomap_v2\Dish_turning\Dish_1_experiment_v1

echo.
echo Training Dish_1 with 300K iterations and aggressive hyperparameters...
echo (This will generate the "Hedgehog" overfitted model for your thesis)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

python train_glomap.py -s "%DISH_DIR%" -m "%OUT_DIR%" -r 1 --iterations 300000 --position_lr_max_steps 300000 --opacity_lr 0.05 --opacity_reset_interval 30000 --densify_grad_threshold 0.00006 --densify_until_iter 250000 --eval --checkpoint_iterations 100000 200000 300000

echo Optimizing for WebAR (Using old 0.05 opacity pruning)...
python optimize_webar.py -i "%OUT_DIR%\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\point_cloud\iteration_best\point_cloud_web_v1.ply" --opacity 0.05

echo.
echo ==========================================
echo EXPERIMENT V1 SAVED TO: %OUT_DIR%
echo ==========================================
