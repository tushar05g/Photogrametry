#!/usr/bin/env node
/**
 * Generate 25 high-quality images of a 3D mouse object using Three.js
 * with headless browser rendering for photogrammetry pipeline testing.
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const outputDir = '/home/harpreet/Documents/3d_scanner/assets/mouse_threejs_images';
const numImages = 25;
const imageSize = 1024;

// Create output directory
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

// Generate camera positions for 360° coverage
function generateCameraPositions(num) {
    const positions = [];
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    
    for (let i = 0; i < num; i++) {
        const elevation = -30 + (i / (num - 1)) * 90;
        const azimuth = (i * goldenAngle * 180 / Math.PI) % 360;
        positions.push({ elevation, azimuth });
    }
    
    return positions;
}

async function generateImages() {
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const page = await browser.newPage();
    await page.setViewport({ width: imageSize, height: imageSize });
    
    const cameraPositions = generateCameraPositions(numImages);
    
    console.log(`Generating ${numImages} images using Three.js...`);
    
    for (let i = 0; i < cameraPositions.length; i++) {
        const { elevation, azimuth } = cameraPositions[i];
        console.log(`Rendering image ${i + 1}/${numImages}: elevation=${elevation.toFixed(1)}°, azimuth=${azimuth.toFixed(1)}°`);
        
        // Create HTML with Three.js scene
        const html = `
<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; overflow: hidden; background: #f0f0f0; }
        canvas { display: block; }
    </style>
</head>
<body>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0xf0f0f0);
        
        const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 1000);
        camera.position.set(0, 0, 6);
        
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(${imageSize}, ${imageSize});
        renderer.setPixelRatio(window.devicePixelRatio);
        document.body.appendChild(renderer.domElement);
        
        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambientLight);
        
        const directionalLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight1.position.set(5, -5, 5);
        scene.add(directionalLight1);
        
        const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.4);
        directionalLight2.position.set(-5, -5, 3);
        scene.add(directionalLight2);
        
        const directionalLight3 = new THREE.DirectionalLight(0xffffff, 0.3);
        directionalLight3.position.set(0, 5, 2);
        scene.add(directionalLight3);
        
        // Mouse body - rounded cube
        const bodyGeometry = new THREE.BoxGeometry(3, 1.8, 0.8);
        const bodyMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x1a3240,
            roughness: 0.4,
            metalness: 0.05
        });
        const body = new THREE.Mesh(bodyGeometry, bodyMaterial);
        scene.add(body);
        
        // Left button
        const buttonGeometry = new THREE.BoxGeometry(0.7, 0.4, 0.15);
        const buttonMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x1a1a1a,
            roughness: 0.3
        });
        const leftButton = new THREE.Mesh(buttonGeometry, buttonMaterial);
        leftButton.position.set(-0.8, 0.5, 0.2);
        scene.add(leftButton);
        
        // Right button
        const rightButton = new THREE.Mesh(buttonGeometry, buttonMaterial);
        rightButton.position.set(0.8, 0.5, 0.2);
        scene.add(rightButton);
        
        // Scroll wheel
        const wheelGeometry = new THREE.CylinderGeometry(0.15, 0.15, 0.3, 32);
        const wheelMaterial = new THREE.MeshStandardMaterial({ 
            color: 0x0d0d0d,
            roughness: 0.2
        });
        const scrollWheel = new THREE.Mesh(wheelGeometry, wheelMaterial);
        scrollWheel.rotation.x = Math.PI / 2;
        scrollWheel.position.set(0, 0.6, 0.35);
        scene.add(scrollWheel);
        
        // DPI light
        const lightGeometry = new THREE.SphereGeometry(0.08, 32, 32);
        const lightMaterial = new THREE.MeshBasicMaterial({ 
            color: 0xcc3333
        });
        const dpiLight = new THREE.Mesh(lightGeometry, lightMaterial);
        dpiLight.position.set(0, 0.7, 0.2);
        scene.add(dpiLight);
        
        // Logo area
        const logoGeometry = new THREE.BoxGeometry(0.8, 0.4, 0.02);
        const logoMaterial = new THREE.MeshStandardMaterial({ 
            color: 0xcccccc,
            roughness: 0.2,
            metalness: 0.3
        });
        const logoArea = new THREE.Mesh(logoGeometry, logoMaterial);
        logoArea.position.set(0, -0.3, 0.45);
        scene.add(logoArea);
        
        // Set camera position
        const elevRad = ${elevation} * Math.PI / 180;
        const azimRad = ${azimuth} * Math.PI / 180;
        camera.position.x = 6 * Math.cos(elevRad) * Math.cos(azimRad);
        camera.position.y = 6 * Math.cos(elevRad) * Math.sin(azimRad);
        camera.position.z = 6 * Math.sin(elevRad);
        camera.lookAt(0, 0, 0);
        
        renderer.render(scene, camera);
    </script>
</body>
</html>
        `;
        
        await page.setContent(html);
        
        // Wait for rendering
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Screenshot
        const outputPath = path.join(outputDir, `mouse_threejs_${String(i + 1).padStart(2, '0')}_e${Math.round(elevation)}_a${Math.round(azimuth)}.png`);
        await page.screenshot({ path: outputPath });
        console.log(`  Saved to ${outputPath}`);
    }
    
    await browser.close();
    console.log(`\\n✅ Generated ${numImages} images in ${outputDir}`);
}

generateImages().catch(console.error);
