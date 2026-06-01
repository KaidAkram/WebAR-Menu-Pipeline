@echo off
echo ==========================================
echo FINALIZING POUTIN AND TRAINING PERFECT PIZZA & SANDWITCH
echo ==========================================

set CONDA_PATH=C:\anaconda3
call "%CONDA_PATH%\Scripts\activate.bat" gaussian_splatting

set BASE_DIR=D:\GLOMAP
set OUT_DIR=D:\3DGS\gaussian-splatting\output\GLOMAP

echo ==========================================
echo [1/3] Saving Best Poutin (Iteration 40000)
echo ==========================================
:: Compress the highest available iteration for poutin before it was stopped
python compress_splats.py -i "%OUT_DIR%\poutin_300k\point_cloud\iteration_40000\point_cloud.ply" -o "%OUT_DIR%\poutin_300k\point_cloud\iteration_40000\point_cloud.splat"

echo Preparing GLOMAP directories for Pizza and Sandwitch...
if exist "%BASE_DIR%\pizza\pizza\frames_final" rename "%BASE_DIR%\pizza\pizza\frames_final" images
if exist "%BASE_DIR%\pizza\pizza\sparse_model" rename "%BASE_DIR%\pizza\pizza\sparse_model" sparse
if exist "%BASE_DIR%\sandwitch\sandwitch\frames_final" rename "%BASE_DIR%\sandwitch\sandwitch\frames_final" images
if exist "%BASE_DIR%\sandwitch\sandwitch\sparse_model" rename "%BASE_DIR%\sandwitch\sandwitch\sparse_model" sparse

echo ==========================================
echo Cleaning up any old Pizza and Sandwitch runs...
echo ==========================================
if exist "%OUT_DIR%\pizza_300k" rmdir /s /q "%OUT_DIR%\pizza_300k"
if exist "%OUT_DIR%\sandwitch_300k" rmdir /s /q "%OUT_DIR%\sandwitch_300k"

echo ==========================================
echo [2/3] Training GLOMAP Pizza (Perfect 300K)...
echo ==========================================
python train_glomap.py -s "%BASE_DIR%\pizza\pizza" -m "%OUT_DIR%\pizza_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 --checkpoint_iterations 100000 200000 300000
echo Compressing Pizza Splats...
python compress_splats.py -i "%OUT_DIR%\pizza_300k\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\pizza_300k\point_cloud\iteration_best\point_cloud.splat"

echo ==========================================
echo [3/3] Training GLOMAP Sandwitch (Perfect 300K)...
echo ==========================================
python train_glomap.py -s "%BASE_DIR%\sandwitch\sandwitch" -m "%OUT_DIR%\sandwitch_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 --checkpoint_iterations 100000 200000 300000
echo Compressing Sandwitch Splats...
python compress_splats.py -i "%OUT_DIR%\sandwitch_300k\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\sandwitch_300k\point_cloud\iteration_best\point_cloud.splat"

echo ==========================================
echo PERFECT TRAINING PIPELINE COMPLETE.
echo ==========================================
pause
