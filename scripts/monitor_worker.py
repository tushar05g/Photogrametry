#!/usr/bin/env python3
"""
Worker progress monitoring script for Morphic 3D Scanner
"""

import requests
import json
import time
import sys
from datetime import datetime

# Configuration
NGROK_URL = "https://ollie-unfashionable-topographically.ngrok-free.dev"
API_BASE = f"{NGROK_URL}/api/v1"

def get_all_jobs():
    """Get all jobs from the API"""
    try:
        response = requests.get(f"{NGROK_URL}/scans/", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"❌ Error fetching jobs: {e}")
    return []

def get_job_status(job_id):
    """Get specific job status"""
    try:
        response = requests.get(f"{NGROK_URL}/scans/{job_id}/progress", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"❌ Error fetching job {job_id}: {e}")
    return None

def print_job_status(job):
    """Print formatted job status"""
    status_emoji = {
        'pending': '⏳',
        'processing': '⚙️',
        'completed': '✅',
        'failed': '❌'
    }
    
    emoji = status_emoji.get(job.get('status', '❓')
    progress = job.get('progress', 0)
    project = job.get('project_name', 'Unknown')
    created = job.get('created_at', 'Unknown')
    
    print(f"\n{emoji} Job: {job.get('id', 'Unknown')}")
    print(f"📝 Project: {project}")
    print(f"📊 Status: {job.get('status', 'Unknown')} ({progress}%)")
    print(f"📅 Created: {created}")
    
    if job.get('error_message'):
        print(f"❌ Error: {job['error_message']}")
    
    if job.get('model_url'):
        print(f"🎲 Model: {NGROK_URL}{job['model_url']}")
    
    print("-" * 50)

def monitor_specific_job(job_id):
    """Monitor a specific job in real-time"""
    print(f"🔍 Monitoring job: {job_id}")
    print("=" * 50)
    
    last_progress = -1
    
    try:
        while True:
            job = get_job_status(job_id)
            if not job:
                print("❌ Failed to get job status")
                break
            
            current_progress = job.get('progress', 0)
            
            # Only print if progress changed
            if current_progress != last_progress:
                print(f"\n🕐 {datetime.now().strftime('%H:%M:%S')} - {job.get('status', 'Unknown')} ({current_progress}%)")
                
                if job.get('warnings'):
                    print(f"⚠️ Warning: {job['warnings']}")
                
                if job.get('error_message'):
                    print(f"❌ Error: {job['error_message']}")
                
                if job.get('status') == 'completed':
                    print(f"🎉 Job completed! Model: {NGROK_URL}{job.get('model_url', '')}")
                    break
                elif job.get('status') == 'failed':
                    print(f"💀 Job failed: {job.get('error_message', 'Unknown error')}")
                    break
                
                last_progress = current_progress
            
            time.sleep(3)  # Check every 3 seconds
            
    except KeyboardInterrupt:
        print("\n👋 Stopped monitoring")

def monitor_all_jobs():
    """Show all jobs and their status"""
    print("📊 All Jobs Status")
    print("=" * 50)
    
    jobs = get_all_jobs()
    if not jobs:
        print("📭 No jobs found")
        return
    
    for job in jobs:
        print_job_status(job)

def main():
    """Main monitoring interface"""
    print("🔍 Morphic 3D Scanner Worker Monitor")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        job_id = sys.argv[1]
        monitor_specific_job(job_id)
    else:
        while True:
            print("\n📋 Options:")
            print("1. Show all jobs")
            print("2. Monitor specific job")
            print("3. Exit")
            
            choice = input("\nSelect option (1-3): ").strip()
            
            if choice == '1':
                monitor_all_jobs()
            elif choice == '2':
                job_id = input("Enter Job ID: ").strip()
                if job_id:
                    monitor_specific_job(job_id)
            elif choice == '3':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice")

if __name__ == "__main__":
    main()
