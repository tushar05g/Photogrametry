# 🚀 Photogrammetry Pipeline Refactor Roadmap

## 📋 Progress Tracking

| Step | Task | Status | Details |
| :--- | :--- | :--- | :--- |
| 1 | Identified Issues in Current Code | ✅ Completed | State leakage & storage coupling identified |
| 2 | Storage Abstraction Layer | ✅ Completed | `StorageProvider` with S3, Local, Modal implementations |
| 3 | DB Integration (Neon) | ✅ Completed | Models in place, status.json references removed |
| 4 | Task Refactor (Celery Pipeline) | ✅ Completed | Granular, resumable tasks using DB status |
| 5 | Modal Worker Refactor | ✅ Completed | Updated GPU functions with abstraction |
| 6 | Integration | ✅ Completed | All components using standard path structure |
| 7 | Validation | ⏳ In Progress | Running end-to-end tests |

---

## 🔍 Validation Results
- **Storage Layer**: Switching `STORAGE_TYPE` between local/s3/modal works in theory via factory.
- **Resumability**: Pipeline successfully skips completed stages.
- **Consistency**: Standardized paths: `jobs/{job_id}/input/preprocessed/`, `jobs/{job_id}/output/sparse/`, etc.
