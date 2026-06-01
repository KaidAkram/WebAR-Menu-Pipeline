@echo off
cd /d "%~dp0\.."
echo ==========================================
echo FINALIZING SANDWITCH AND TRAINING PIZZA
echo ==========================================

set CONDA_PATH=C:\anaconda3
call "%CONDA_PATH%\Scripts\activate.bat" gaussian_splatting

set BASE_DIR=D:\GLOMAP
set OUT_DIR=D:\3DGS\gaussian-splatting\output\GLOMAP

echo ==========================================
echo [1/2] Saving Best Sandwitch (Iteration 165000)
echo ==========================================
:: Compress the highest available iteration for sandwitch before it was stopped
python compress_splats.py -i "%OUT_DIR%\sandwitch_300k\point_cloud\iteration_165000\point_cloud.ply" -o "%OUT_DIR%\sandwitch_300k\point_cloud\iteration_165000\point_cloud.splat"

echo ==========================================
echo Cleaning up Pizza folder...
echo ==========================================
if exist "%OUT_DIR%\pizza_300k" rmdir /s /q "%OUT_DIR%\pizza_300k"

echo ==========================================
echo [2/2] Training GLOMAP Pizza (Perfect 300K)...
echo ==========================================
:: Fixed the source path for pizza. The GLOMAP/pizza folder was missing the sparse point cloud.
:: Using the correctly processed pizza dataset located in D:\2CS\coolmap_pizza\coolmap_pizza
python train_glomap.py -s "D:\2CS\coolmap_pizza\coolmap_pizza" -m "%OUT_DIR%\pizza_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 --checkpoint_iterations 100000 200000 300000
echo Compressing Pizza Splats...
python compress_splats.py -i "%OUT_DIR%\pizza_300k\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\pizza_300k\point_cloud\iteration_best\point_cloud.splat"

echo ==========================================
echo TRAINING PIPELINE COMPLETE.
echo ==========================================
pause
