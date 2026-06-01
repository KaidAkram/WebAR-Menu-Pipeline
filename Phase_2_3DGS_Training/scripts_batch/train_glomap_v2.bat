@echo off
cd /d "%~dp0\.."
setlocal enabledelayedexpansion

echo ==========================================
echo GLOMAP V2: 6 DISHES PRODUCTION PIPELINE
echo ==========================================

set CONDA_PATH=C:\anaconda3
call "%CONDA_PATH%\Scripts\activate.bat" gaussian_splatting

set SRC_BASE=D:\glomap_pipeline\glomap_pipeline\processed_data
set SPARSE_SRC=D:\glomap_pipeline\glomap_pipeline\outputs
set OUT_BASE=D:\3DGS\gaussian-splatting\output\glomap_v2

:: Define the strategies and dishes (Me_walking removed to prevent 20-day GPU Thrashing)
set STRATEGIES=Dish_turning
set DISHES=Dish_1 Dish_2 Dish_3

echo.
echo [PHASE 1] Data Unification...
echo ==========================================

for %%S in (%STRATEGIES%) do (
    for %%D in (%DISHES%) do (
        set DISH_DIR=%SRC_BASE%\%%S\%%D
        set SPARSE_DIR=!DISH_DIR!\sparse
        set SPARSE_ORIGIN=%SPARSE_SRC%\%%S\%%D\sparse
        
        if exist "!DISH_DIR!" (
            rem 1. Rename frames_final to images if needed
            if exist "!DISH_DIR!\frames_final" (
                echo Renaming frames_final to images in %%S\%%D...
                rename "!DISH_DIR!\frames_final" images
            )
            
            rem 2. Copy sparse geometry from outputs to processed_data
            if not exist "!SPARSE_DIR!" (
                if exist "!SPARSE_ORIGIN!" (
                    echo Copying sparse geometry for %%S\%%D...
                    xcopy /E /I /Q "!SPARSE_ORIGIN!" "!SPARSE_DIR!"
                ) else (
                    echo WARNING: No sparse geometry found for %%S\%%D at !SPARSE_ORIGIN!
                )
            ) else (
                echo Sparse geometry already unified for %%S\%%D.
            )
            
            rem 3. Heal the sparse folder structure - 3DGS mathematically requires a '0' subfolder
            if not exist "!SPARSE_DIR!\0" (
                echo Healing sparse folder structure for %%S\%%D - creating 0 directory...
                mkdir "!SPARSE_DIR!\0"
                rem Safely move all loose files from sparse\ into sparse\0\
                move "!SPARSE_DIR!\*.*" "!SPARSE_DIR!\0\" >nul 2>&1
            )
        ) else (
            echo WARNING: Source directory not found: !DISH_DIR!
        )
    )
)

echo.
echo [PHASE 2] 3DGS Training ^& WebAR Optimization...
echo ==========================================

for %%S in (%STRATEGIES%) do (
    for %%D in (%DISHES%) do (
        set DISH_DIR=%SRC_BASE%\%%S\%%D
        set OUT_DIR=%OUT_BASE%\%%S\%%D
        
        if exist "!DISH_DIR!\images" (
            if exist "!DISH_DIR!\sparse" (
                echo.
                echo ------------------------------------------
                echo Training: %%S / %%D
                echo ------------------------------------------
                
                if exist "!OUT_DIR!\point_cloud\iteration_best\point_cloud_web.ply" (
                    echo SKIPPING %%S / %%D: Already fully trained and optimized!
                ) else (
                    rem Create target directory
                    if not exist "!OUT_DIR!" mkdir "!OUT_DIR!"
                    
                    rem Run 30K Enhanced Detail Training - Experiment 3
                    python train_glomap.py -s "!DISH_DIR!" -m "!OUT_DIR!" -r 1 --iterations 30000 --densify_grad_threshold 0.0001 --densify_until_iter 25000 --eval --checkpoint_iterations 30000
                    
                    rem Run WebAR Optimization
                    echo Optimizing %%S / %%D for WebAR...
                    python optimize_webar.py -i "!OUT_DIR!\point_cloud\iteration_best\point_cloud.ply" -o "!OUT_DIR!\point_cloud\iteration_best\point_cloud_web.ply"
                )
            ) else (
                echo SKIPPING %%S\%%D: Missing 'sparse' directory.
            )
        ) else (
            echo SKIPPING %%S\%%D: Missing 'images' directory.
        )
    )
)

echo ==========================================
echo GLOMAP V2 PIPELINE COMPLETE!
echo ==========================================
