@echo off
cd /d "%~dp0\.."
echo ==========================================
echo WEBAR MENU: MIDDLE GROUND EXPERIMENT (100k+)
echo THRESHOLD: 0.00006 (TACTICAL AGGRESSION)
echo ==========================================

set CONDA_PATH=C:\anaconda3
call "%CONDA_PATH%\Scripts\activate.bat" gaussian_splatting

set BASE_DIR=D:\2CS
set OLD_OUT=D:\3DGS\gaussian-splatting\output\coolmap_pizza_300k
set NEW_OUT=D:\3DGS\gaussian-splatting\output\Middle_Ground_100k

:: EXPERIMENT CONFIG:
:: Loading from the 100k Baseline
:: Saving to Middle_Ground_100k
:: Using Aggressive Densification (0.00006)

python train.py ^
    -s "%BASE_DIR%\coolmap_pizza\coolmap_pizza" ^
    -m "%NEW_OUT%" ^
    -r 2 ^
    --iterations 300000 ^
    --start_checkpoint "%OLD_OUT%\chkpnt100000.pth" ^
    --eval ^
    --densify_grad_threshold 0.00006 ^
    --densify_until_iter 250000

echo ==========================================
echo Packing and compressing final model for Mobile WebAR...
python compress_splats.py -i "%NEW_OUT%\point_cloud\iteration_300000\point_cloud.ply" -o "%NEW_OUT%\point_cloud\iteration_300000\point_cloud.splat"
echo ==========================================

pause

