import os
import sys
import argparse
import numpy as np
from plyfile import PlyData

def convert_ply_to_splat(ply_path, splat_path):
    print(f"Reading PLY file from: {ply_path}...")
    try:
        plydata = PlyData.read(ply_path)
    except Exception as e:
        print(f"Error reading PLY: {e}")
        return False
    
    vert = plydata["vertex"]
    num_splats = len(vert)
    print(f"Loaded {num_splats:,} splats from PLY.")
    
    # 1. Extract properties safely in vector format
    print("Extracting vertex attributes...")
    x = np.asarray(vert["x"], dtype=np.float32)
    y = np.asarray(vert["y"], dtype=np.float32)
    z = np.asarray(vert["z"], dtype=np.float32)
    
    scale_0 = np.asarray(vert["scale_0"], dtype=np.float32)
    scale_1 = np.asarray(vert["scale_1"], dtype=np.float32)
    scale_2 = np.asarray(vert["scale_2"], dtype=np.float32)
    
    rot_0 = np.asarray(vert["rot_0"], dtype=np.float32)
    rot_1 = np.asarray(vert["rot_1"], dtype=np.float32)
    rot_2 = np.asarray(vert["rot_2"], dtype=np.float32)
    rot_3 = np.asarray(vert["rot_3"], dtype=np.float32)
    
    opacity = np.asarray(vert["opacity"], dtype=np.float32)
    
    f_dc_0 = np.asarray(vert["f_dc_0"], dtype=np.float32)
    f_dc_1 = np.asarray(vert["f_dc_1"], dtype=np.float32)
    f_dc_2 = np.asarray(vert["f_dc_2"], dtype=np.float32)
    
    # 2. Sort splats by size * opacity (standard sorting for optimal alpha blending & depth sorting baseline)
    print("Sorting splats for optimal transparency rendering...")
    opacity_sig = 1.0 / (1.0 + np.exp(-opacity))
    scale_sum = np.exp(scale_0 + scale_1 + scale_2)
    sorting_val = scale_sum * opacity_sig
    sorted_indices = np.argsort(-sorting_val)
    
    # Apply sorting
    x, y, z = x[sorted_indices], y[sorted_indices], z[sorted_indices]
    scale_0, scale_1, scale_2 = scale_0[sorted_indices], scale_1[sorted_indices], scale_2[sorted_indices]
    rot_0, rot_1, rot_2, rot_3 = rot_0[sorted_indices], rot_1[sorted_indices], rot_2[sorted_indices], rot_3[sorted_indices]
    f_dc_0, f_dc_1, f_dc_2 = f_dc_0[sorted_indices], f_dc_1[sorted_indices], f_dc_2[sorted_indices]
    opacity_sig = opacity_sig[sorted_indices]
    
    # 3. Vectorized calculations for .splat format
    print("Computing positions and scales...")
    position = np.stack([x, y, z], axis=1)
    scale = np.stack([np.exp(scale_0), np.exp(scale_1), np.exp(scale_2)], axis=1)
    
    print("Converting Spherical Harmonics to RGB...")
    SH_C0 = 0.28209479177387814
    r = (0.5 + SH_C0 * f_dc_0) * 255.0
    g = (0.5 + SH_C0 * f_dc_1) * 255.0
    b = (0.5 + SH_C0 * f_dc_2) * 255.0
    a = opacity_sig * 255.0
    color = np.stack([r, g, b, a], axis=1)
    color = np.clip(color, 0, 255).astype(np.uint8)
    
    print("Normalizing and quantizing rotations...")
    rot = np.stack([rot_0, rot_1, rot_2, rot_3], axis=1)
    norm = np.linalg.norm(rot, axis=1, keepdims=True)
    norm = np.where(norm == 0.0, 1.0, norm)
    rot = rot / norm
    
    # Quantize rotation quaternion [-1.0, 1.0] to [0, 255]
    rot_quant = (rot * 127.5 + 127.5)
    rot_quant = np.clip(rot_quant, 0, 255).astype(np.uint8)
    
    # 4. Binary packing into structure
    print("Packing binary data...")
    splat_data = np.zeros(num_splats, dtype=[
        ('position', 'f4', 3),
        ('scale', 'f4', 3),
        ('color', 'u1', 4),
        ('rot', 'u1', 4)
    ])
    
    splat_data['position'] = position
    splat_data['scale'] = scale
    splat_data['color'] = color
    splat_data['rot'] = rot_quant
    
    print(f"Writing compressed splats to: {splat_path}...")
    with open(splat_path, "wb") as f:
        f.write(splat_data.tobytes())
        
    orig_size = os.path.getsize(ply_path) / (1024 * 1024)
    new_size = os.path.getsize(splat_path) / (1024 * 1024)
    reduction = (1 - (new_size / orig_size)) * 100
    
    print("=" * 40)
    print("COMPRESSION SUCCESSFUL!")
    print(f"Original PLY: {orig_size:.2f} MB")
    print(f"Compressed SPLAT: {new_size:.2f} MB")
    print(f"Reduction Ratio: {reduction:.2f}%")
    print("=" * 40)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert 3DGS PLY files to high-performance .splat files.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input PLY file.")
    parser.add_argument("-o", "--output", required=True, help="Path to the output SPLAT file.")
    args = parser.parse_args()
    
    convert_ply_to_splat(args.input, args.output)
