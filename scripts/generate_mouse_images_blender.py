#!/usr/bin/env blender -b -P
"""
Generate 25 high-quality images of a 3D mouse object from multiple angles
for photogrammetry pipeline testing using Blender.
Run with: blender -b -P generate_mouse_images_blender.py
"""

import bpy
import math
import os
from pathlib import Path
import mathutils

# Configuration
output_dir = Path("/home/harpreet/Documents/3d_scanner/assets/mouse_images")
output_dir.mkdir(exist_ok=True)

num_images = 25
image_size = 1024
overlap_percentage = 0.6  # 60% overlap

def clear_scene():
    """Clear all objects from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def setup_lighting():
    """Setup good lighting for photogrammetry."""
    # Clear existing lights
    bpy.ops.object.select_by_type(type='LIGHT')
    bpy.ops.object.delete()
    
    # Add three-point lighting
    # Key light
    key_light = bpy.data.lights.new(name="KeyLight", type='POINT')
    key_light.energy = 1000
    key_light_obj = bpy.data.objects.new(name="KeyLight", object_data=key_light)
    bpy.context.collection.objects.link(key_light_obj)
    key_light_obj.location = (5, -5, 5)
    
    # Fill light
    fill_light = bpy.data.lights.new(name="FillLight", type='POINT')
    fill_light.energy = 500
    fill_light_obj = bpy.data.objects.new(name="FillLight", object_data=fill_light)
    bpy.context.collection.objects.link(fill_light_obj)
    fill_light_obj.location = (-5, -5, 3)
    
    # Back light
    back_light = bpy.data.lights.new(name="BackLight", type='POINT')
    back_light.energy = 300
    back_light_obj = bpy.data.objects.new(name="BackLight", object_data=back_light)
    bpy.context.collection.objects.link(back_light_obj)
    back_light_obj.location = (0, 5, 2)
    
    # Ambient light
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs['Strength'].default_value = 0.5

def create_mouse_object():
    """Create a realistic 3D mouse object with proper details."""
    # Mouse body - use a more realistic shape using multiple primitives
    # Main body - elongated cube with rounded edges
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    body = bpy.context.active_object
    body.name = "MouseBody"
    body.scale = (3, 1.8, 0.8)
    
    # Add bevel modifier for rounded edges
    bevel = body.modifiers.new(name="Bevel", type='BEVEL')
    bevel.width = 0.15
    bevel.segments = 8
    bevel.profile = 0.5
    
    # Add subsurface modifier for smoothness
    subsurf = body.modifiers.new(name="Subsurf", type='SUBSURF')
    subsurf.levels = 2
    subsurf.render_levels = 3
    
    # Create detailed material with texture
    mat = bpy.data.materials.new(name="MouseMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    # Get principled BSDF
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (0.15, 0.2, 0.25, 1)  # Dark blue-gray
    bsdf.inputs['Roughness'].default_value = 0.4
    bsdf.inputs['Metallic'].default_value = 0.05
    
    # Add multiple noise textures for surface detail
    noise_node1 = nodes.new('ShaderNodeTexNoise')
    noise_node1.location = (-600, 200)
    noise_node1.inputs['Scale'].default_value = 15
    noise_node1.inputs['Detail'].default_value = 8
    
    noise_node2 = nodes.new('ShaderNodeTexNoise')
    noise_node2.location = (-600, 100)
    noise_node2.inputs['Scale'].default_value = 30
    noise_node2.inputs['Detail'].default_value = 4
    
    # Mix noise textures
    mix_node = nodes.new('ShaderNodeMixRGB')
    mix_node.location = (-400, 150)
    mix_node.inputs['Fac'].default_value = 0.5
    
    mat.node_tree.links.new(noise_node1.outputs['Color'], mix_node.inputs['Color1'])
    mat.node_tree.links.new(noise_node2.outputs['Color'], mix_node.inputs['Color2'])
    mat.node_tree.links.new(mix_node.outputs['Color'], bsdf.inputs['Base Color'])
    
    body.data.materials.append(mat)
    
    # Left button - more realistic shape
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.8, 0.5, 0.2))
    left_button = bpy.context.active_object
    left_button.name = "LeftButton"
    left_button.scale = (0.7, 0.4, 0.15)
    
    # Add bevel for rounded edges
    btn_bevel1 = left_button.modifiers.new(name="Bevel", type='BEVEL')
    btn_bevel1.width = 0.05
    btn_bevel1.segments = 6
    
    btn_mat = bpy.data.materials.new(name="ButtonMaterial")
    btn_mat.use_nodes = True
    btn_nodes = btn_mat.node_tree.nodes
    btn_bsdf = btn_nodes.get('Principled BSDF')
    btn_bsdf.inputs['Base Color'].default_value = (0.1, 0.1, 0.1, 1)  # Dark gray
    btn_bsdf.inputs['Roughness'].default_value = 0.3
    left_button.data.materials.append(btn_mat)
    
    # Right button
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.8, 0.5, 0.2))
    right_button = bpy.context.active_object
    right_button.name = "RightButton"
    right_button.scale = (0.7, 0.4, 0.15)
    
    btn_bevel2 = right_button.modifiers.new(name="Bevel", type='BEVEL')
    btn_bevel2.width = 0.05
    btn_bevel2.segments = 6
    right_button.data.materials.append(btn_mat)
    
    # Scroll wheel - more detailed with ridges
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.3, location=(0, 0.6, 0.35))
    scroll_wheel = bpy.context.active_object
    scroll_wheel.name = "ScrollWheel"
    scroll_wheel.rotation_euler = (math.pi/2, 0, 0)
    
    # Add ridges to scroll wheel using wireframe modifier
    wireframe = scroll_wheel.modifiers.new(name="Wireframe", type='WIREFRAME')
    wireframe.thickness = 0.02
    wireframe.use_boundary = True
    
    wheel_mat = bpy.data.materials.new(name="WheelMaterial")
    wheel_mat.use_nodes = True
    wheel_nodes = wheel_mat.node_tree.nodes
    wheel_bsdf = wheel_nodes.get('Principled BSDF')
    wheel_bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1)  # Very dark
    wheel_bsdf.inputs['Roughness'].default_value = 0.2
    scroll_wheel.data.materials.append(wheel_mat)
    
    # Mouse wheel divider line
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.6, 0.35))
    divider = bpy.context.active_object
    divider.name = "WheelDivider"
    divider.scale = (0.3, 0.02, 0.35)
    divider.data.materials.append(btn_mat)
    
    # DPI indicator light
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.08, location=(0, 0.7, 0.2))
    dpi_light = bpy.context.active_object
    dpi_light.name = "DPILight"
    
    light_mat = bpy.data.materials.new(name="LightMaterial")
    light_mat.use_nodes = True
    light_nodes = light_mat.node_tree.nodes
    light_bsdf = light_nodes.get('Principled BSDF')
    # Check if Emission input exists, if not use Base Color with high emission
    if 'Emission' in light_bsdf.inputs:
        light_bsdf.inputs['Emission'].default_value = (0.8, 0.2, 0.2, 1)  # Red glow
        if 'Emission Strength' in light_bsdf.inputs:
            light_bsdf.inputs['Emission Strength'].default_value = 5.0
    else:
        light_bsdf.inputs['Base Color'].default_value = (0.8, 0.2, 0.2, 1)
    dpi_light.data.materials.append(light_mat)
    
    # Mouse cable - more realistic with USB connector
    bpy.ops.curve.primitive_bezier_curve_add(location=(1.5, -1.2, 0))
    cable = bpy.context.active_object
    cable.name = "MouseCable"
    
    # Add bevel to make it a tube
    cable_bevel = cable.modifiers.new(name="Bevel", type='BEVEL')
    cable_bevel.width = 0.06
    cable_bevel.segments = 12
    
    # Curve the cable realistically
    cable.data.dimensions = '3D'
    cable.data.resolution_u = 16
    
    # Add more curve points for realistic cable shape
    spline = cable.data.splines[0]
    spline.bezier_points.add(3)
    
    points = spline.bezier_points
    points[0].co = (1.5, -1.2, 0)
    points[0].handle_left = (1.5, -1.5, 0)
    points[0].handle_right = (1.5, -0.9, 0)
    
    points[1].co = (1.8, -2.0, 0.2)
    points[1].handle_left = (1.6, -1.8, 0)
    points[1].handle_right = (2.0, -2.2, 0.2)
    
    points[2].co = (2.0, -3.0, 0)
    points[2].handle_left = (1.8, -2.8, 0)
    points[2].handle_right = (2.2, -3.2, 0)
    
    points[3].co = (2.5, -4.0, 0.1)
    points[3].handle_left = (2.3, -3.8, 0)
    points[3].handle_right = (2.7, -4.2, 0)
    
    cable_mat = bpy.data.materials.new(name="CableMaterial")
    cable_mat.use_nodes = True
    cable_nodes = cable_mat.node_tree.nodes
    cable_bsdf = cable_nodes.get('Principled BSDF')
    cable_bsdf.inputs['Base Color'].default_value = (0.08, 0.08, 0.08, 1)  # Black
    cable_bsdf.inputs['Roughness'].default_value = 0.6
    cable.data.materials.append(cable_mat)
    
    # USB connector
    bpy.ops.mesh.primitive_cube_add(size=1, location=(2.5, -4.0, 0))
    usb = bpy.context.active_object
    usb.name = "USBConnector"
    usb.scale = (0.4, 0.6, 0.25)
    
    usb_bevel = usb.modifiers.new(name="Bevel", type='BEVEL')
    usb_bevel.width = 0.05
    usb_bevel.segments = 4
    usb.data.materials.append(cable_mat)
    
    # Add brand/logo area on mouse body
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.3, 0.45))
    logo_area = bpy.context.active_object
    logo_area.name = "LogoArea"
    logo_area.scale = (0.8, 0.4, 0.02)
    
    logo_mat = bpy.data.materials.new(name="LogoMaterial")
    logo_mat.use_nodes = True
    logo_nodes = logo_mat.node_tree.nodes
    logo_bsdf = logo_nodes.get('Principled BSDF')
    logo_bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)  # White/silver
    logo_bsdf.inputs['Roughness'].default_value = 0.2
    logo_bsdf.inputs['Metallic'].default_value = 0.3
    logo_area.data.materials.append(logo_mat)
    
    return body

def setup_camera():
    """Setup camera for rendering."""
    # Create camera
    camera_data = bpy.data.cameras.new("Camera")
    camera_obj = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera_obj)
    
    # Set camera as active
    bpy.context.scene.camera = camera_obj
    
    # Set camera properties
    camera_data.sensor_fit = 'AUTO'
    camera_data.sensor_width = 36
    camera_data.lens = 50  # 50mm lens
    
    return camera_obj

def generate_camera_positions(num_images, overlap=0.6):
    """
    Generate camera positions for 360° coverage with specified overlap.
    Uses Fibonacci sphere distribution for even coverage.
    """
    positions = []
    
    # Golden angle for even distribution
    golden_angle = math.pi * (3 - math.sqrt(5))
    
    for i in range(num_images):
        # Elevation: vary from -45 to +60 degrees to get top, bottom, and sides
        elevation = -45 + (i / (num_images - 1)) * 105
        
        # Azimuth: full 360° rotation with overlap
        azimuth = (i * golden_angle * 180 / math.pi) % 360
        
        # Calculate camera distance based on overlap
        # For 60% overlap, we need appropriate spacing
        distance = 6  # Distance from object
        
        positions.append({
            'elevation': elevation,
            'azimuth': azimuth,
            'distance': distance
        })
    
    return positions

def set_camera_position(camera_obj, elevation, azimuth, distance):
    """Set camera position using spherical coordinates."""
    # Convert to radians
    elev_rad = math.radians(elevation)
    azim_rad = math.radians(azimuth)
    
    # Calculate position
    x = distance * math.cos(elev_rad) * math.cos(azim_rad)
    y = distance * math.cos(elev_rad) * math.sin(azim_rad)
    z = distance * math.sin(elev_rad)
    
    camera_obj.location = (x, y, z)
    
    # Make camera look at origin
    direction = mathutils.Vector((0, 0, 0)) - camera_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera_obj.rotation_euler = rot_quat.to_euler()

def setup_render_settings():
    """Setup render settings for high-quality output."""
    scene = bpy.context.scene
    
    # Render settings
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = image_size
    scene.render.resolution_y = image_size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16'
    
    # Cycles settings
    scene.cycles.device = 'CPU'  # Use CPU for compatibility
    scene.cycles.samples = 64  # Reduced for faster rendering without denoising
    scene.cycles.use_denoising = False  # Disabled - not available in this build
    scene.cycles.max_bounces = 4  # Reduced for speed
    scene.cycles.transparent_min_bounces = 4
    scene.cycles.transparent_max_bounces = 8
    
    # Film settings
    scene.cycles.film_exposure = 1.0
    scene.cycles.film_width = 36.0

def main():
    """Main function to generate images."""
    print(f"Generating {num_images} images of 3D mouse object...")
    
    # Clear scene
    clear_scene()
    
    # Setup lighting
    setup_lighting()
    
    # Create mouse object
    create_mouse_object()
    
    # Setup camera
    camera_obj = setup_camera()
    
    # Setup render settings
    setup_render_settings()
    
    # Generate camera positions
    camera_positions = generate_camera_positions(num_images, overlap_percentage)
    
    # Render images
    scene = bpy.context.scene
    for i, pos in enumerate(camera_positions):
        print(f"Rendering image {i+1}/{num_images}: elevation={pos['elevation']:.1f}°, azimuth={pos['azimuth']:.1f}°")
        
        # Set camera position
        set_camera_position(camera_obj, pos['elevation'], pos['azimuth'], pos['distance'])
        
        # Set output path
        output_path = output_dir / f"mouse_{i+1:02d}_e{int(pos['elevation'])}_a{int(pos['azimuth'])}.png"
        scene.render.filepath = str(output_path)
        
        # Render
        bpy.ops.render.render(write_still=True)
        print(f"  Saved to {output_path}")
    
    print(f"\n✅ Generated {num_images} images in {output_dir}")

if __name__ == "__main__":
    main()
