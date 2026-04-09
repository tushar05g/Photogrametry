#!/bin/bash

# Photogrammetry Cube Test Script v2.0
# This script automates testing the photogrammetry system using cube images
# Updated to support progressive uploads, splatting toggles, and comparison tests.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="http://localhost:8000"
ASSETS_DIR="assets/cube_images"
SPLAT_ENABLED="true"

# Check for jq
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is not installed. Please install it to use this script.${NC}"
    exit 1
fi

# Function to check system status
check_system_status() {
    echo -e "${YELLOW}Checking system status...${NC}"
    
    # Check backend
    HEALTH=$(curl -s "$BACKEND_URL/health" || echo "offline")
    if [[ "$HEALTH" == *"status"* ]] || [[ "$HEALTH" == *"ok"* ]]; then
        echo -e "${GREEN}✓ Backend is online${NC}"
    else
        echo -e "${RED}✗ Backend is not responding at $BACKEND_URL${NC}"
        return 1
    fi
    
    # Check Redis
    if redis-cli ping &>/dev/null; then
        echo -e "${GREEN}✓ Redis is running${NC}"
    else
        echo -e "${RED}✗ Redis is not running${NC}"
        return 1
    fi
    
    echo ""
    return 0
}

# Function to get project name with timestamp
get_project_name() {
    local base=$1
    echo "${base} $(date +%H%M%S)"
}

# Base upload function
upload_job() {
    local project_name=$1
    shift
    local images=("$@")
    
    echo -e "${YELLOW}Initiating bulk upload...${NC}"
    echo "Project: $project_name"
    echo "Images: ${#images[@]}"
    echo "Splatting: $SPLAT_ENABLED"
    
    CURL_CMD=("curl" "-s" "-X" "POST" "$BACKEND_URL/api/v1/jobs/upload")
    CURL_CMD+=("-F" "project_name=$project_name")
    CURL_CMD+=("-F" "enable_splat=$SPLAT_ENABLED")
    
    for img in "${images[@]}"; do
        if [ -f "$img" ]; then
            CURL_CMD+=("-F" "files=@$img")
        fi
    done
    
    RESPONSE=$("${CURL_CMD[@]}")
    
    JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id // empty')
    
    if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "null" ]; then
        echo -e "${GREEN}✓ Upload successful${NC}"
        echo "Job ID: $JOB_ID"
        echo "$JOB_ID" > /tmp/cube_test_job_id.txt
        return 0
    else
        echo -e "${RED}✗ Upload failed${NC}"
        echo "Response: $RESPONSE"
        return 1
    fi
}

# Progressive upload function
progressive_upload() {
    local project_name=$1
    shift
    local images=("$@")
    
    echo -e "${YELLOW}Starting progressive upload...${NC}"
    echo "Project: $project_name"
    
    # 1. Initialize
    INIT_RESP=$(curl -s -X POST "$BACKEND_URL/api/v1/jobs/init" -F "project_name=$project_name")
    JOB_ID=$(echo "$INIT_RESP" | jq -r '.job_id // empty')
    
    if [ -z "$JOB_ID" ] || [ "$JOB_ID" == "null" ]; then
        echo -e "${RED}✗ Initialization failed${NC}"
        echo "$INIT_RESP"
        return 1
    fi
    
    echo -e "${GREEN}✓ Job initialized: $JOB_ID${NC}"
    
    # 2. Sequential upload
    local count=0
    for img in "${images[@]}"; do
        if [ -f "$img" ]; then
            count=$((count + 1))
            echo -ne "\rUploading image $count/${#images[@]}... "
            UPLOAD_RESP=$(curl -s -X POST "$BACKEND_URL/api/v1/jobs/$JOB_ID/upload-single" -F "file=@$img")
            if [[ "$UPLOAD_RESP" != *"success"* ]]; then
                echo -e "\n${RED}✗ Failed to upload $img${NC}"
                return 1
            fi
        fi
    done
    echo -e "${GREEN}Done.${NC}"
    
    # 3. Start pipeline
    echo -e "${YELLOW}Triggering pipeline (Splatting: $SPLAT_ENABLED)...${NC}"
    START_RESP=$(curl -s -X POST "$BACKEND_URL/api/v1/jobs/$JOB_ID/start?enable_splat=$SPLAT_ENABLED")
    
    if [[ "$START_RESP" == *"started"* ]]; then
        echo -e "${GREEN}✓ Pipeline started successfully${NC}"
        echo "$JOB_ID" > /tmp/cube_test_job_id.txt
        return 0
    else
        echo -e "${RED}✗ Failed to start pipeline${NC}"
        echo "$START_RESP"
        return 1
    fi
}

# Monitoring function
monitor_job() {
    local job_id=$1
    [ -z "$job_id" ] && return 1
    
    echo -e "${YELLOW}Monitoring job: $job_id${NC}"
    echo "Press Ctrl+C to stop monitoring"
    echo ""
    
    local last_stage=""
    while true; do
        STATUS_JSON=$(curl -s "$BACKEND_URL/api/v1/scans/$job_id/status")
        
        # Check if curl failed
        if [ $? -ne 0 ] || [ -z "$STATUS_JSON" ]; then
            echo -e "${RED}Error fetching status${NC}"
            sleep 5
            continue
        fi
        
        # Parse fields
        STATUS=$(echo "$STATUS_JSON" | jq -r '.status // "UNKNOWN"')
        STAGE=$(echo "$STATUS_JSON" | jq -r '.current_stage // "IDLE"')
        MSG=$(echo "$STATUS_JSON" | jq -r '.message // ""')
        
        # Only print if stage changed or status changed
        if [ "$STAGE" != "$last_stage" ] || [ "$STATUS" == "COMPLETED" ] || [ "$STATUS" == "FAILED" ]; then
            echo -e "[$(date +%H:%M:%S)] Status: ${BLUE}$STATUS${NC} | Stage: ${CYAN}$STAGE${NC}"
            [ -n "$MSG" ] && [ "$MSG" != "null" ] && echo "  Note: $MSG"
            last_stage=$STAGE
        fi
        
        if [ "$STATUS" == "COMPLETED" ]; then
            echo -e "\n${GREEN}✓ Job finished successfully!${NC}"
            return 0
        elif [ "$STATUS" == "FAILED" ]; then
            echo -e "\n${RED}✗ Job failed${NC}"
            return 1
        fi
        
        sleep 5
    done
}

# Results function
get_results() {
    local job_id=$1
    echo -e "${YELLOW}Retrieving results for $job_id...${NC}"
    
    RESULTS_JSON=$(curl -s "$BACKEND_URL/api/v1/scans/$job_id/results")
    
    # Check for artifacts
    MODEL_URL=$(echo "$RESULTS_JSON" | jq -r '.model_url // empty')
    SPLAT_URL=$(echo "$RESULTS_JSON" | jq -r '.splat_url // empty')
    
    echo -e "${BLUE}--- Artifact Check ---${NC}"
    if [ -n "$MODEL_URL" ]; then
        echo -e "Mesh Model: ${GREEN}Detected${NC} ($MODEL_URL)"
    else
        echo -e "Mesh Model: ${RED}Missing${NC}"
    fi
    
    if [ -n "$SPLAT_URL" ]; then
        echo -e "Gaussian Splat: ${GREEN}Detected${NC} ($SPLAT_URL)"
    else
        echo -e "Gaussian Splat: ${YELLOW}Not Generated${NC}"
    fi
    echo -e "${BLUE}----------------------${NC}"
    
    echo "Full JSON results:"
    echo "$RESULTS_JSON" | jq .
    echo ""
}

# Scenario 7: Comparison logic
run_comparison_test() {
    echo -e "${MAGENTA}=== Scenario 7: Mesh vs. Splat Comparison ===${NC}"
    
    # ALL images
    local images=("$ASSETS_DIR"/*.png)
    
    # Job 1: With Splatting
    echo -e "\n${YELLOW}Step 1: Starting Job WITH Splatting...${NC}"
    SPLAT_ENABLED="true"
    upload_job "Compare_WITH_Splat" "${images[@]}"
    JOB_A=$(cat /tmp/cube_test_job_id.txt)
    
    # Job 2: Without Splatting
    echo -e "\n${YELLOW}Step 2: Starting Job WITHOUT Splatting...${NC}"
    SPLAT_ENABLED="false"
    upload_job "Compare_WITHOUT_Splat" "${images[@]}"
    JOB_B=$(cat /tmp/cube_test_job_id.txt)
    
    echo -e "\n${GREEN}Both jobs initiated!${NC}"
    echo "Job A (Splat): $JOB_A"
    echo "Job B (Mesh Only): $JOB_B"
    echo ""
    echo "You can now monitor them individually."
    SPLAT_ENABLED="true" # Reset to default
}

# Main menu
main_menu() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Photogrammetry Cube Test Suite v2.0   ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Splatting Enabled: $([ "$SPLAT_ENABLED" == "true" ] && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}")"
    echo -e "Assets Directory: ${CYAN}$ASSETS_DIR${NC}"
    echo -e "${BLUE}----------------------------------------${NC}"
    echo "1) Full Cube (All 18 images) - Bulk Upload"
    echo "2) Minimum Set (cube 1-3) - Bulk Upload"
    echo "3) Partial Coverage (cube 1-5) - Bulk Upload"
    echo "4) Progressive Upload Test (All images, sequential)"
    echo "5) Scenario 7: Comparison (Splat vs No-Splat)"
    echo -e "${BLUE}----------------------------------------${NC}"
    echo "s) Toggle Splatting Generation"
    echo "m) Monitor existing job"
    echo "r) Get job results"
    echo "h) Check system health"
    echo "q) Quit"
    echo ""
}

# Execution
main() {
    check_system_status || true
    
    while true; do
        main_menu
        read -p "Selection: " choice
        
        case $choice in
            1)
                upload_job "$(get_project_name "Full_Cube")" "$ASSETS_DIR"/*.png
                [ $? -eq 0 ] && monitor_job "$(cat /tmp/cube_test_job_id.txt)" && get_results "$(cat /tmp/cube_test_job_id.txt)"
                ;;
            2)
                upload_job "$(get_project_name "Min_Set")" "$ASSETS_DIR"/cube1.png "$ASSETS_DIR"/cube2.png "$ASSETS_DIR"/cube3.png
                [ $? -eq 0 ] && monitor_job "$(cat /tmp/cube_test_job_id.txt)" && get_results "$(cat /tmp/cube_test_job_id.txt)"
                ;;
            3)
                upload_job "$(get_project_name "Partial")" "$ASSETS_DIR"/cube1.png "$ASSETS_DIR"/cube2.png "$ASSETS_DIR"/cube3.png "$ASSETS_DIR"/cube4.png "$ASSETS_DIR"/cube5.png
                [ $? -eq 0 ] && monitor_job "$(cat /tmp/cube_test_job_id.txt)" && get_results "$(cat /tmp/cube_test_job_id.txt)"
                ;;
            4)
                progressive_upload "$(get_project_name "Progressive")" "$ASSETS_DIR"/*.png
                [ $? -eq 0 ] && monitor_job "$(cat /tmp/cube_test_job_id.txt)" && get_results "$(cat /tmp/cube_test_job_id.txt)"
                ;;
            5)
                run_comparison_test
                ;;
            s)
                if [ "$SPLAT_ENABLED" == "true" ]; then SPLAT_ENABLED="false"; else SPLAT_ENABLED="true"; fi
                echo -e "${YELLOW}Splatting toggled to: $SPLAT_ENABLED${NC}"
                ;;
            m)
                read -p "Job ID: " jid
                monitor_job "$jid"
                ;;
            r)
                read -p "Job ID: " jid
                get_results "$jid"
                ;;
            h)
                check_system_status
                ;;
            q)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid selection${NC}"
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
        clear
    done
}

# Start
main
