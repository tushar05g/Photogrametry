#!/usr/bin/env python3
"""
Ngrok status monitor for Morphic 3D Scanner
"""

import requests
import json
import time
import sys

def get_ngrok_url():
    """Get the current ngrok public URL"""
    try:
        response = requests.get('http://127.0.0.1:4040/api/tunnels')
        if response.status_code == 200:
            data = response.json()
            if data['tunnels']:
                return data['tunnels'][0]['public_url']
    except:
        pass
    return None

def main():
    """Monitor and display ngrok status"""
    print("🌐 Ngrok Status Monitor")
    print("=" * 40)
    
    url = get_ngrok_url()
    if url:
        print(f"✅ Ngrok URL: {url}")
        print(f"📱 Mobile: {url}/frontend/mobile.html")
        print(f"💻 Desktop: {url}/frontend/index.html")
        print(f"📊 API Docs: {url}/docs")
        print(f"❤️ Health: {url}/health")
        print("=" * 40)
        print("🔄 Monitoring... (Ctrl+C to stop)")
        
        try:
            while True:
                time.sleep(30)
                current_url = get_ngrok_url()
                if current_url != url:
                    print(f"🔄 URL changed: {current_url}")
                    url = current_url
        except KeyboardInterrupt:
            print("\n👋 Stopped monitoring")
    else:
        print("❌ Ngrok not running or not accessible")
        print("Start ngrok with: ngrok http 8000")
        sys.exit(1)

if __name__ == "__main__":
    main()
