#!/usr/bin/env python3
"""
Startup script for the complete Morphic 3D Scanner system
"""

import os
import sys
import subprocess
import time
import signal
import threading
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configuration
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8001
WORKER_PROCESSES = 1

class SystemManager:
    def __init__(self):
        self.processes = {}
        self.running = True
    
    def start_redis(self) -> bool:
        """Start Redis server"""
        print("🔴 Starting Redis server...")
        try:
            # Check if Redis is already running
            result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True)
            if result.returncode == 0 and 'PONG' in result.stdout:
                print("✅ Redis is already running")
                return True
            
            # Start Redis
            redis_process = subprocess.Popen(['redis-server'], 
                                           stdout=subprocess.DEVNULL, 
                                           stderr=subprocess.DEVNULL)
            self.processes['redis'] = redis_process
            
            # Wait for Redis to start
            time.sleep(2)
            
            # Check if Redis started successfully
            result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True)
            if result.returncode == 0 and 'PONG' in result.stdout:
                print("✅ Redis started successfully")
                return True
            else:
                print("❌ Failed to start Redis")
                return False
                
        except FileNotFoundError:
            print("❌ Redis not found. Please install Redis: sudo apt-get install redis-server")
            return False
        except Exception as e:
            print(f"❌ Redis startup failed: {e}")
            return False
    
    def start_backend(self) -> bool:
        """Start the FastAPI backend"""
        print("🚀 Starting FastAPI backend...")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root)
            
            backend_process = subprocess.Popen([
                sys.executable, '-m', 'uvicorn', 
                'backend.main:app',
                '--host', str(BACKEND_HOST),
                '--port', str(BACKEND_PORT),
                '--reload'
            ], cwd=str(project_root), env=env)
            
            self.processes['backend'] = backend_process
            
            # Wait for backend to start
            time.sleep(5)
            
            # Check if backend is responding with retries
            import requests
            for attempt in range(5):
                try:
                    response = requests.get(f"http://{BACKEND_HOST}:{BACKEND_PORT}/health", timeout=5)
                    if response.status_code == 200:
                        print(f"✅ Backend started at http://{BACKEND_HOST}:{BACKEND_PORT}")
                        return True
                    else:
                        print(f"⚠️ Backend health check returned {response.status_code}, retrying...")
                except requests.RequestException as e:
                    print(f"⚠️ Backend not responding (attempt {attempt+1}/5): {e}")
                
                time.sleep(2)
            
            print("❌ Backend failed to respond after multiple attempts")
            return False
                
        except Exception as e:
            print(f"❌ Backend startup failed: {e}")
            return False
    
    def start_worker(self) -> bool:
        """Start the CPU worker"""
        print("⚙️ Starting CPU worker...")
        try:
            # Use the new worker structure
            worker_script = project_root / "core" / "workers" / "cpu_worker.py"
            env = os.environ.copy()
            env["PYTHONPATH"] = str(project_root)
            
            worker_process = subprocess.Popen([
                sys.executable, '-m', 'core.workers.cpu_worker'
            ], cwd=str(project_root), env=env)
            
            self.processes['worker'] = worker_process
            print("✅ Worker started")
            return True
            
        except Exception as e:
            print(f"❌ Worker startup failed: {e}")
            return False
    
    def stop_all(self):
        """Stop all processes"""
        print("\n🛑 Stopping all services...")
        self.running = False
        
        for name, process in self.processes.items():
            try:
                if process.poll() is None:  # Process is still running
                    print(f"Stopping {name}...")
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"✅ {name} stopped")
            except subprocess.TimeoutExpired:
                print(f"Force killing {name}...")
                process.kill()
            except Exception as e:
                print(f"Error stopping {name}: {e}")
    
    def run(self):
        """Run the complete system"""
        print("🎲 Morphic 3D Scanner System Startup")
        print("=" * 50)
        
        # Check if we're in the right directory
        if not (project_root / 'backend' / 'main.py').exists():
            print("❌ Error: backend/main.py not found. Please run from project root.")
            return
        
        # Set up signal handlers
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}. Shutting down...")
            self.stop_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start services
        services = [
            ("Redis", self.start_redis),
            ("Backend", self.start_backend),
            ("Worker", self.start_worker)
        ]
        
        for service_name, start_func in services:
            if not start_func():
                print(f"❌ Failed to start {service_name}. Shutting down...")
                self.stop_all()
                return
        
        print("\n🎉 All services started successfully!")
        print("=" * 50)
        print(f"🌐 Backend API: http://{BACKEND_HOST}:{BACKEND_PORT}")
        print(f"📤 Frontend: file://{project_root}/frontend/index.html")
        print(f"📊 API Docs: http://{BACKEND_HOST}:{BACKEND_PORT}/docs")
        print(f"📁 Sample Images: {project_root}/assets/sample_images/cube/")
        print("=" * 50)
        print("🔄 System is running. Press Ctrl+C to stop.")
        
        # Monitor processes
        try:
            while self.running:
                # Check if any process died
                for name, process in list(self.processes.items()):
                    if process.poll() is not None:
                        print(f"⚠️ {name} process died unexpectedly")
                        # Try to restart it
                        if name == 'backend':
                            print("🔄 Restarting backend...")
                            self.start_backend()
                        elif name == 'worker':
                            print("🔄 Restarting worker...")
                            self.start_worker()
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all()

def main():
    """Main entry point"""
    manager = SystemManager()
    manager.run()

if __name__ == "__main__":
    main()
