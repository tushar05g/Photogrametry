# 🎲 Morphic 3D Scanner

A high-performance, distributed 3D scanning platform using photogrammetry and advanced computer vision techniques.

## 🎯 Overview

Morphic transforms multiple 2D images into accurate 3D models using a sophisticated CPU-based photogrammetry pipeline. The system features a modern web interface, robust backend API, and scalable worker architecture.

### ✨ Key Features

- **🔄 Dynamic Processing**: Upload images → Generate 3D models → No file proliferation
- **🎯 Web Interface**: Modern drag-and-drop upload with real-time progress
- **⚡ CPU Photogrammetry**: Advanced SfM and MVS pipeline without GPU requirements
- **🏗️ Scalable Architecture**: Redis queue system with background workers
- **📊 Real-time Tracking**: Live job status and progress updates
- **🛡️ Robust Validation**: Image quality checks and error recovery
- **🎨 3D Viewer**: Interactive model display with multiple viewing modes

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   CPU Worker    │
│   (HTML/JS)     │◄──►│   (FastAPI)     │◄──►│  (Photogrammetry)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       ▼
         │                ┌─────────────┐        ┌─────────────┐
         │                │   Redis     │        │  PostgreSQL │
         │                │   Queue     │        │   Database  │
         │                └─────────────┘        └─────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   User Images   │    │   3D Models     │
│   (Upload)      │    │   (Output)      │
└─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
morphic-3d-scanner/
├── 📁 backend/                    # FastAPI backend
│   ├── api/
│   │   ├── scans.py              # Scan management endpoints
│   │   ├── upload.py             # Direct image upload
│   │   └── models.py             # Model download/view
│   ├── core/                      # Configuration & database
│   ├── models/                    # SQLAlchemy models
│   ├── services/                  # Business logic
│   └── main.py                    # FastAPI application
├── 📁 frontend/                   # Web frontend
│   ├── index.html                 # Main application UI
│   ├── js/                        # JavaScript modules
│   ├── css/                       # Stylesheets
│   ├── viewer/                    # 3D viewer components
│   └── assets/                    # Static assets
├── 📁 core/                       # Shared core functionality
│   ├── photogrammetry/            # 3D reconstruction pipeline
│   │   ├── pipeline.py            # Main pipeline class
│   │   ├── validation.py          # Image validation
│   │   └── meshing.py             # Mesh generation
│   ├── workers/                   # Background workers
│   │   ├── cpu_worker.py          # CPU photogrammetry worker
│   │   └── base_worker.py         # Base worker class
│   └── utils/                     # Utility modules
│       ├── logger.py              # Logging utilities
│       ├── file_utils.py          # File operations
│       └── api_utils.py           # API utilities
├── 📁 scripts/                    # Utility scripts
│   └── start.py                   # System startup script
├── 📁 assets/                     # Static assets
│   └── sample_images/             # Sample datasets
│       └── cube/                  # Cube images (20 files)
├── 📁 output/                     # Generated 3D models
├── 📄 requirements.txt             # Python dependencies
├── 📄 .env.example                # Environment template
├── 📄 .gitignore                  # Git ignore rules
└── 📄 README.md                   # This file
```

## � Quick Start

### Method 1: One-Command Startup

```bash
python scripts/start.py
```

This starts:
- ✅ Redis server
- ✅ FastAPI backend
- ✅ CPU worker
- ✅ Auto-restart on failures

### Method 2: Manual Startup

1. **Start Redis:**
```bash
redis-server
```

2. **Start Backend:**
```bash
source .venv/bin/activate
cd backend
python main.py
```

3. **Start Worker:**
```bash
source .venv/bin/activate
python core/workers/cpu_worker.py
```

## 🌐 Access Points

### Frontend Interface
- **Main UI**: `frontend/index.html`
- **Features**: Drag & drop upload, real-time status, 3D model viewer

### Backend API
- **Base URL**: `http://localhost:8000`
- **API Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

## � API Endpoints

### Upload Images Directly
```bash
curl -X POST http://localhost:8000/api/v1/images \
  -F "files=@image1.jpg" \
  -F "files=@image2.jpg" \
  -F "files=@image3.jpg" \
  -F "project_name=My Object"
```

### Check Job Status
```bash
curl http://localhost:8000/scans/{job_id}/progress
```

### Download 3D Model
```bash
curl http://localhost:8000/api/v1/job/{job_id}/download
```

## 🔄 Processing Workflow

### 1. Image Upload
- **Validation**: File type, size, quantity checks
- **Quality Assessment**: Blur detection, resolution validation
- **Storage**: Temporary local processing

### 2. Job Creation
- **Database**: Creates job record with metadata
- **Queue**: Adds job to Redis queue for processing
- **Tracking**: Returns job ID for status monitoring

### 3. 3D Reconstruction
- **Feature Extraction**: SIFT keypoint detection
- **Feature Matching**: Pairwise image matching
- **SfM**: Structure from Motion camera pose estimation
- **MVS**: Multi-View Stereo dense reconstruction
- **Meshing**: Surface reconstruction and optimization

### 4. Model Delivery
- **Storage**: Model saved to `/output/` directory
- **Database**: Job updated with model URL
- **Frontend**: Real-time status updates + model display

## 📊 Frontend Features

### Upload Interface
- 🎯 **Drag & Drop**: Intuitive file upload
- 📸 **Image Preview**: Thumbnail grid with remove option
- 📝 **Project Naming**: Custom project names
- ⚡ **Real-time Validation**: Immediate feedback

### Status Tracking
- 📊 **Progress Bar**: Visual processing status
- 🔄 **Live Updates**: Auto-refresh every 2 seconds
- ⚠️ **Error Handling**: Clear error messages
- ✅ **Success Notifications**: Completion alerts

### 3D Model Viewer
- 🎲 **Interactive Display**: Rotate, zoom, pan
- 📐 **Multiple Views**: Wireframe, solid, rainbow modes
- 🎮 **Controls**: Adjustable rotation speed
- 📱 **Responsive**: Works on all devices

## � Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/morphic

# Redis
REDIS_URL=redis://localhost:6379

# Backend Settings
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
```

### Processing Requirements
- **Min Images**: 3 (for basic reconstruction)
- **Max Images**: 50 (to prevent overload)
- **File Size**: 10MB per image
- **Formats**: JPG, PNG, WebP
- **Recommended**: 8-20 images for best results

## 🛠️ Development

### Setup Development Environment
```bash
# Clone repository
git clone https://github.com/your-username/morphic-3d-scanner.git
cd morphic-3d-scanner

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Start development server
python scripts/start.py
```

### Project Structure Guidelines

#### Core Modules (`core/`)
- **photogrammetry/**: 3D reconstruction logic
- **workers/**: Background job processors
- **utils/**: Shared utility functions

#### Backend (`backend/`)
- **api/**: REST API endpoints
- **models/**: Database models
- **services/**: Business logic

#### Frontend (`frontend/`)
- **js/**: Modular JavaScript components
- **css/**: Stylesheets
- **viewer/**: 3D visualization components

### Adding New Features

1. **New Processing Pipeline**: Add to `core/photogrammetry/`
2. **New API Endpoints**: Add to `backend/api/`
3. **New Worker Types**: Add to `core/workers/`
4. **Frontend Components**: Add to `frontend/js/`

## 📊 Performance

### Processing Time
- **Small objects** (3-8 images): 1-3 minutes
- **Medium objects** (8-20 images): 3-8 minutes
- **Large objects** (20-50 images): 8-15 minutes

### System Requirements
- **CPU**: 4+ cores recommended
- **RAM**: 8GB+ recommended
- **Storage**: 1GB+ free space
- **Network**: Stable internet for API communication

## 🔍 Monitoring

### Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Redis status
redis-cli ping

# Worker logs
tail -f logs/worker.log
```

### Database Queries
```sql
-- Active jobs
SELECT * FROM scan_jobs WHERE status IN ('pending', 'processing');

-- Job history
SELECT * FROM scan_jobs ORDER BY created_at DESC LIMIT 10;

-- Processing statistics
SELECT status, COUNT(*) FROM scan_jobs GROUP BY status;
```

## 🚨 Troubleshooting

### Common Issues

**Redis Connection Failed**
```bash
# Install Redis
sudo apt-get install redis-server

# Start Redis
redis-server

# Check status
redis-cli ping
```

**Backend Not Responding**
```bash
# Check logs
cd backend && python main.py

# Verify port
netstat -tulpn | grep :8000
```

**Worker Crashes**
```bash
# Check worker logs
tail -f logs/worker.log

# Restart worker
python core/workers/cpu_worker.py
```

**3D Model Generation Failed**
- Use 8-20 images per object
- Ensure 60-80% overlap between images
- Good lighting and contrast
- Object fills 50-70% of frame
- Multiple angles (top, bottom, sides)

## 🎯 Best Practices

### For Users
- Upload 8-20 high-quality images
- Ensure good lighting and focus
- Capture multiple angles
- Avoid motion blur
- Use consistent background

### For Developers
- Monitor system resources
- Implement error handling
- Use progress indicators
- Validate inputs thoroughly
- Handle concurrent requests

### For Operations
- Monitor Redis queue length
- Set up log rotation
- Implement backup strategies
- Monitor database performance
- Set up alerts for failures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [COLMAP](https://github.com/colmap/colmap) - Structure from Motion
- [Open3D](http://www.open3d.org/) - 3D data processing
- [Three.js](https://threejs.org/) - 3D web graphics
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Redis](https://redis.io/) - Queue management

---

**🎲 Transform your images into 3D models with Morphic!**

Built with ❤️ by the Morphic team