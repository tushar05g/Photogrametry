import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';

class MorphicViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.currentMesh = null;
        
        this.init();
        this.animate();
        this.handleResize();
    }

    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0f172a);
        
        // Premium Fog for depth
        this.scene.fog = new THREE.FogExp2(0x0f172a, 0.1);

        // Camera
        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.set(0, 2, 5);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ReinhardToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        this.container.appendChild(this.renderer.domElement);

        // Controls
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.autoRotate = false;
        this.controls.autoRotateSpeed = 1.0;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        const mainLight = new THREE.DirectionalLight(0xffffff, 1.2);
        mainLight.position.set(5, 10, 7.5);
        this.scene.add(mainLight);

        const fillLight = new THREE.PointLight(0x6366f1, 0.8);
        fillLight.position.set(-5, 2, -5);
        this.scene.add(fillLight);

        // Grid/Floor
        const grid = new THREE.GridHelper(20, 40, 0x1e293b, 0x1e293b);
        grid.position.y = -1;
        this.scene.add(grid);

        // Placeholder
        this.addPlaceholder();
    }

    addPlaceholder() {
        const geometry = new THREE.IcosahedronGeometry(1, 4);
        const material = new THREE.MeshPhysicalMaterial({
            color: 0x6366f1,
            wireframe: true,
            transparent: true,
            opacity: 0.3,
            roughness: 0,
            metalness: 0.5
        });
        this.currentMesh = new THREE.Mesh(geometry, material);
        this.scene.add(this.currentMesh);
    }

    async loadModel(url, type = 'ply') {
        const loader = type === 'ply' ? new PLYLoader() : new OBJLoader();
        
        console.log(`Loading ${type} model from:`, url);
        
        try {
            if (this.currentMesh) this.scene.remove(this.currentMesh);

            const object = await new Promise((resolve, reject) => {
                loader.load(url, resolve, undefined, reject);
            });

            let mesh;
            if (type === 'ply') {
                object.computeVertexNormals();
                const material = new THREE.MeshStandardMaterial({ 
                    vertexColors: object.hasAttribute('color'),
                    roughness: 0.5,
                    metalness: 0.2
                });
                mesh = new THREE.Mesh(object, material);
            } else {
                mesh = object;
            }

            // Center and Scale
            const box = new THREE.Box3().setFromObject(mesh);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 3 / maxDim;
            mesh.scale.setScalar(scale);
            
            mesh.position.sub(center.multiplyScalar(scale));
            mesh.position.y += 1; // Sit on grid

            this.currentMesh = mesh;
            this.scene.add(this.currentMesh);
            
            // Adjust camera
            this.camera.position.set(0, 2, 5);
            this.controls.target.set(0, 1, 0);
            
        } catch (error) {
            console.error("Failed to load model:", error);
            alert("Failed to load 3D model. Check console for details.");
        }
    }

    toggleAutoRotate() {
        this.controls.autoRotate = !this.controls.autoRotate;
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    handleResize() {
        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });
    }
}

// Global instance for UI interaction
window.viewer = new MorphicViewer('view-container');

// Load model from URL if present
const params = new URLSearchParams(window.location.search);
const model = params.get('model');
const type = params.get('type') || 'ply';
if (model) {
    window.viewer.loadModel(model, type);
}
