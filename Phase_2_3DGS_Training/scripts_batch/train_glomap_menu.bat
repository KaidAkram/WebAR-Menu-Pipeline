@echo off
cd /d "%~dp0\.."
echo ==========================================
echo GLOMAP MENU: 300K PRODUCTION TRAINING
echo ==========================================

set CONDA_PATH=C:\anaconda3
call "%CONDA_PATH%\Scripts\activate.bat" gaussian_splatting

set BASE_DIR=D:\GLOMAP
set OUT_DIR=D:\3DGS\gaussian-splatting\output\GLOMAP

:: 1. Structure the GLOMAP output folders to match 3DGS expectations
:: 3DGS train.py expects 'images' and 'sparse/0'
echo Preparing GLOMAP directories...

if exist "%BASE_DIR%\burger\burger\frames_final" rename "%BASE_DIR%\burger\burger\frames_final" images
if exist "%BASE_DIR%\burger\burger\sparse_model" rename "%BASE_DIR%\burger\burger\sparse_model" sparse

if exist "%BASE_DIR%\pizza\pizza\frames_final" rename "%BASE_DIR%\pizza\pizza\frames_final" images
if exist "%BASE_DIR%\pizza\pizza\sparse_model" rename "%BASE_DIR%\pizza\pizza\sparse_model" sparse

if exist "%BASE_DIR%\poutin\poutin\frames_final" rename "%BASE_DIR%\poutin\poutin\frames_final" images
if exist "%BASE_DIR%\poutin\poutin\sparse_model" rename "%BASE_DIR%\poutin\poutin\sparse_model" sparse

if exist "%BASE_DIR%\sandwitch\sandwitch\frames_final" rename "%BASE_DIR%\sandwitch\sandwitch\frames_final" images
if exist "%BASE_DIR%\sandwitch\sandwitch\sparse_model" rename "%BASE_DIR%\sandwitch\sandwitch\sparse_model" sparse

:: 2. Sequential Training Pipeline using 'train_glomap.py'
:: Golden Hyperparameters: 300K iter, -r 2, thresh 0.00006, densify until 250000

echo ==========================================
echo [1/4] Training GLOMAP Burger (300K)...
echo ==========================================
python train_glomap.py -s "%BASE_DIR%\burger\burger" -m "%OUT_DIR%\burger_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 --checkpoint_iterations 100000 200000 300000
echo Compressing Burger Splats...
python optimize_webar.py -i "%OUT_DIR%\burger_300k\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\burger_300k\point_cloud\iteration_best\point_cloud_web.ply"

echo ==========================================
echo [2/4] Training GLOMAP Pizza (300K)...
echo ==========================================
python train_glomap.py -s "%BASE_DIR%\pizza\pizza" -m "%OUT_DIR%\pizza_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 --checkpoint_iterations 100000 200000 300000
echo Compressing Pizza Splats...
python optimize_webar.py -i "%OUT_DIR%\pizza_300k\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\pizza_300k\point_cloud\iteration_best\point_cloud_web.ply"

echo ==========================================
echo [3/4] Training GLOMAP Poutin (300K)...
echo ==========================================
python train_glomap.py -s "%BASE_DIR%\poutin\poutin" -m "%OUT_DIR%\poutin_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 --checkpoint_iterations 100000 200000 300000
echo Compressing Poutin Splats...
python optimize_webar.py -i "%OUT_DIR%\poutin_300k\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\poutin_300k\point_cloud\iteration_best\point_cloud_web.ply"

echo ==========================================
echo [4/4] Training GLOMAP Sandwitch (300K)...
echo ==========================================
python train_glomap.py -s "%BASE_DIR%\sandwitch\sandwitch" -m "%OUT_DIR%\sandwitch_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00006 --densify_until_iter 250000 --checkpoint_iterations 100000 200000 300000
echo Compressing Sandwitch Splats...
python optimize_webar.py -i "%OUT_DIR%\sandwitch_300k\point_cloud\iteration_best\point_cloud.ply" -o "%OUT_DIR%\sandwitch_300k\point_cloud\iteration_best\point_cloud_web.ply"

echo ==========================================
echo GLOMAP 300K PRODUCTION PIPELINE COMPLETE.
echo ==========================================
