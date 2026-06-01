import open3d as o3d
import os

# 1. Define your file paths (Replace with the path to your best .ply file)
# Note: Use the final .ply BEFORE you converted it to .splat
input_ply = r"C:\3DGS\gaussian-splatting\output\run_60k_r2_optimized\point_cloud\iteration_60000\point_cloud.ply"
output_obj = r"C:\Users\Akram KAID\Desktop\2CS_project\submission(5)\project\proxy_collider.obj"

print("Loading high-density point cloud...")
pcd = o3d.io.read_point_cloud(input_ply)

# 2. Downsample the cloud (Crucial for WebAR performance)
# We don't need millions of points for a simple click-target. 
print("Downsampling data for mobile optimization...")
downpcd = pcd.voxel_down_sample(voxel_size=0.05)

# 3. Calculate the Convex Hull (The invisible "shrink-wrap" mesh)
print("Calculating physical boundaries (Convex Hull)...")
hull_mesh, _ = downpcd.compute_convex_hull()

# 4. Clean up and export the mesh
hull_mesh.compute_vertex_normals()
o3d.io.write_triangle_mesh(output_obj, hull_mesh)

print(f"Success! Proxy mesh saved to: {output_obj}")