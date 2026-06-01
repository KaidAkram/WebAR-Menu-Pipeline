import os
import sys
import argparse
import numpy as np
from plyfile import PlyData, PlyElement

def optimize_ply_for_webar(ply_path, out_path, sh_degree=2, prune_opacity_threshold=0.005):
    print(f"Reading High-Fidelity PLY file from: {ply_path}...")
    try:
        plydata = PlyData.read(ply_path)
    except Exception as e:
        print(f"Error reading PLY: {e}")
        return False
    
    vert = plydata["vertex"]
    num_splats = len(vert)
    print(f"Loaded {num_splats:,} splats from PLY.")
    
    # Extract properties
    print("Extracting vertex attributes...")
    properties_to_keep = ['x', 'y', 'z', 'opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
    
    # Always keep base color (SH degree 0)
    properties_to_keep.extend(['f_dc_0', 'f_dc_1', 'f_dc_2'])
    
    # Add SH degrees based on user selection (WebAR sweet spot is Degree 1)
    if sh_degree >= 1:
        # Degree 1 adds 3 terms per color channel (9 total)
        for i in range(9):
            properties_to_keep.append(f'f_rest_{i}')
            
    if sh_degree >= 2:
        # Degree 2 adds 5 terms per color channel (15 total, cumulative 24)
        for i in range(9, 24):
            properties_to_keep.append(f'f_rest_{i}')
            
    if sh_degree >= 3:
        # Degree 3 adds 7 terms per color channel (21 total, cumulative 45)
        for i in range(24, 45):
            properties_to_keep.append(f'f_rest_{i}')

    # Validate properties exist
    available_props = [p.name for p in vert.properties]
    final_props = [p for p in properties_to_keep if p in available_props]
    
    print(f"Original properties per point: {len(available_props)}")
    print(f"Optimized properties per point: {len(final_props)}")
    
    # Extract data into a dict of arrays
    data = {}
    for prop in final_props:
        data[prop] = np.asarray(vert[prop])
        
    # Spatial Pruning (Remove garbage floaters)
    print(f"Pruning splats with opacity < {prune_opacity_threshold}...")
    # Calculate true alpha from pre-activated opacity (sigmoid)
    alpha = 1.0 / (1.0 + np.exp(-data['opacity']))
    mask = alpha >= prune_opacity_threshold
    
    # Apply the mask
    for prop in final_props:
        data[prop] = data[prop][mask]
        
    new_num_splats = len(data['x'])
    pruned_count = num_splats - new_num_splats
    print(f"Pruned {pruned_count:,} invisible splats ({(pruned_count/num_splats)*100:.1f}% reduction).")
    
    # Construct new PLY Element
    print("Constructing optimized binary payload...")
    dtype_list = [(prop, 'f4') for prop in final_props]
    
    vertex_data = np.empty(new_num_splats, dtype=dtype_list)
    for prop in final_props:
        vertex_data[prop] = data[prop]
        
    el = PlyElement.describe(vertex_data, 'vertex')
    
    print(f"Writing web-ready PLY to: {out_path}...")
    with open(out_path, mode='wb') as f:
        PlyData([el], text=False).write(f)
        
    orig_size = os.path.getsize(ply_path) / (1024 * 1024)
    new_size = os.path.getsize(out_path) / (1024 * 1024)
    reduction = (1 - (new_size / orig_size)) * 100
    
    print("=" * 50)
    print("WEBAR OPTIMIZATION SUCCESSFUL!")
    print(f"Original Points:  {num_splats:,}")
    print(f"Optimized Points: {new_num_splats:,}")
    print(f"Original File:    {orig_size:.2f} MB")
    print(f"Optimized File:   {new_size:.2f} MB")
    print(f"Total Size Reduction: {reduction:.2f}%")
    print("=" * 50)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize 3DGS PLY files for WebAR (PlayCanvas/gsplat) by truncating SH degrees and pruning floaters.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input High-Res PLY file.")
    parser.add_argument("-o", "--output", required=True, help="Path to the output Web-Ready PLY file.")
    parser.add_argument("--sh", type=int, default=2, choices=[0, 1, 2, 3], help="Spherical Harmonics Degree to keep. 2 is best for glossy food. (Default: 2)")
    parser.add_argument("--opacity", type=float, default=0.005, help="Prune splats with alpha below this threshold. (Default: 0.005)")
    args = parser.parse_args()
    
    optimize_ply_for_webar(args.input, args.output, args.sh, args.opacity)
