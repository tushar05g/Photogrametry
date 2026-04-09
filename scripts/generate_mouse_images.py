#!/usr/bin/env python3
"""
Generate 25 high-quality images of a 3D mouse-like object from multiple angles
for photogrammetry pipeline testing.
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import Ellipse, Rectangle
import os
from pathlib import Path

# Create output directory
output_dir = Path("/home/harpreet/Documents/3d_scanner/assets/mouse_images")
output_dir.mkdir(exist_ok=True)

# Image settings
image_size = (1024, 1024)
dpi = 100
num_images = 25

def create_mouse_shape(ax, elevation, azimuth):
    """
    Create a 3D mouse-like shape with good texture for photogrammetry.
    """
    # Clear the axis
    ax.clear()
    
    # Set viewing angle
    ax.view_init(elev=elevation, azim=azimuth)
    
    # Mouse body (ellipsoid)
    u = np.linspace(0, 2 * np.pi, 50)
    v = np.linspace(0, np.pi, 50)
    x = 3 * np.outer(np.cos(u), np.sin(v))
    y = 1.5 * np.outer(np.sin(u), np.sin(v))
    z = 1 * np.outer(np.ones(np.size(u)), np.cos(v))
    
    # Add texture variation with different colors
    colors = plt.cm.viridis(np.linspace(0.2, 0.8, 50))
    for i in range(len(u)):
        ax.plot_surface(x, y, z, color=colors[i % len(colors)], alpha=0.6)
    
    # Mouse buttons (smaller ellipsoids)
    # Left button
    x_btn1 = 0.5 * np.outer(np.cos(u), np.sin(v)) + 1.5
    y_btn1 = 0.3 * np.outer(np.sin(u), np.sin(v))
    z_btn1 = 0.3 * np.outer(np.ones(np.size(u)), np.cos(v)) + 0.5
    ax.plot_surface(x_btn1, y_btn1, z_btn1, color='red', alpha=0.8)
    
    # Right button
    x_btn2 = 0.5 * np.outer(np.cos(u), np.sin(v)) + 2.0
    y_btn2 = 0.3 * np.outer(np.sin(u), np.sin(v))
    z_btn2 = 0.3 * np.outer(np.ones(np.size(u)), np.cos(v)) + 0.5
    ax.plot_surface(x_btn2, y_btn2, z_btn2, color='blue', alpha=0.8)
    
    # Scroll wheel (cylinder)
    theta = np.linspace(0, 2*np.pi, 30)
    z_wheel = np.linspace(-0.3, 0.3, 10)
    theta_grid, z_grid = np.meshgrid(theta, z_wheel)
    x_wheel = 0.2 * np.cos(theta_grid) + 1.75
    y_wheel = 0.2 * np.sin(theta_grid) + 0.3
    ax.plot_surface(x_wheel, y_wheel, z_grid, color='green', alpha=0.9)
    
    # Mouse cable (curved line)
    t = np.linspace(0, 3, 50)
    x_cable = 3 + 0.5 * np.sin(t)
    y_cable = -0.5 * t
    z_cable = 0.5 * np.cos(t)
    ax.plot(x_cable, y_cable, z_cable, color='black', linewidth=3)
    
    # Set limits and remove axes for clean images
    ax.set_xlim(-4, 4)
    ax.set_ylim(-4, 4)
    ax.set_zlim(-2, 2)
    ax.set_axis_off()
    
    # Set background color
    ax.set_facecolor('#f0f0f0')
    
    return ax

def generate_camera_positions(num_images):
    """
    Generate camera positions for 360° coverage with 60%+ overlap.
    Uses Fibonacci sphere distribution for even coverage.
    """
    positions = []
    
    # Golden angle for even distribution
    golden_angle = np.pi * (3 - np.sqrt(5))
    
    for i in range(num_images):
        # Elevation: vary from -30 to +60 degrees to get top, bottom, and sides
        elevation = -30 + (i / (num_images - 1)) * 90
        
        # Azimuth: full 360° rotation
        azimuth = (i * golden_angle * 180 / np.pi) % 360
        
        positions.append((elevation, azimuth))
    
    return positions

def main():
    print(f"Generating {num_images} images of 3D mouse object...")
    
    # Generate camera positions
    camera_positions = generate_camera_positions(num_images)
    
    # Create figure
    fig = plt.figure(figsize=(image_size[0]/dpi, image_size[1]/dpi), dpi=dpi)
    ax = fig.add_subplot(111, projection='3d')
    
    # Generate images
    for i, (elevation, azimuth) in enumerate(camera_positions):
        print(f"Generating image {i+1}/{num_images}: elevation={elevation:.1f}°, azimuth={azimuth:.1f}°")
        
        # Create mouse shape with current camera angle
        create_mouse_shape(ax, elevation, azimuth)
        
        # Save image
        output_path = output_dir / f"mouse_{i+1:02d}_e{int(elevation)}_a{int(azimuth)}.png"
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight', pad_inches=0.1, facecolor='#f0f0f0')
        print(f"  Saved to {output_path}")
    
    plt.close()
    print(f"\n✅ Generated {num_images} images in {output_dir}")

if __name__ == "__main__":
    main()
