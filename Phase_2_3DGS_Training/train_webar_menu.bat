@echo off
echo ==========================================
echo WEBAR MENU: 4-HOUR R2 PRODUCTION
echo ==========================================

set CONDA_PATH=C:\anaconda3
call "%CONDA_PATH%\Scripts\activate.bat" gaussian_splatting

set BASE_DIR=D:\2CS
set OUT_DIR=D:\3DGS\gaussian-splatting\output

:: 4-HOUR R2 CONFIG:
:: Iterations: 300,000
:: Resolution: -r 2
:: Densify until: 200,000
:: Threshold: 0.00008

echo [1/3] Training Pizza (300K R2)...
python train.py -s "%BASE_DIR%\coolmap_pizza\coolmap_pizza" -m "%OUT_DIR%\coolmap_pizza_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00008 --densify_until_iter 200000 --checkpoint_iterations 100000 200000 300000

echo [2/3] Training Sandwich (300K R2)...
python train.py -s "%BASE_DIR%\coolmap_sandwitch\coolmap_sandwitch" -m "%OUT_DIR%\coolmap_sandwitch_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00008 --densify_until_iter 200000 --checkpoint_iterations 100000 200000 300000

echo [3/3] Training Double Plate (300K R2)...
python train.py -s "%BASE_DIR%\platDouble_coolmap\platDouble_coolmap" -m "%OUT_DIR%\platDouble_coolmap_300k" -r 2 --iterations 300000 --eval --densify_grad_threshold 0.00008 --densify_until_iter 200000 --checkpoint_iterations 100000 200000 300000

echo ==========================================
echo 300K R2 PRODUCTION COMPLETE.
echo ==========================================
pause
