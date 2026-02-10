#!/bin/bash
# Test script for add-repo endpoint

set -e

API_URL="http://localhost:8000"

echo "🧪 Testing add-repo endpoint..."
echo ""

# Step 1: Create a test project
echo "1️⃣ Creating test project..."
PROJECT_RESPONSE=$(curl -s -X POST "$API_URL/projects" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Add Repo","description":"Testing GitHub repo cloning"}')

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id')
echo "   ✅ Created project: $PROJECT_ID"
echo ""

# Step 2: Add a repository
echo "2️⃣ Adding repository via GitHub URL..."
REPO_RESPONSE=$(curl -s -X POST "$API_URL/projects/$PROJECT_ID/add-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/anthropics/anthropic-sdk-python"}')

echo "$REPO_RESPONSE" | jq '.'
echo ""

# Step 3: Verify the clone exists
REPO_PATH=$(echo "$REPO_RESPONSE" | jq -r '.repo_path')
echo "3️⃣ Verifying clone at: $REPO_PATH"
if [ -d "$REPO_PATH" ]; then
    echo "   ✅ Clone directory exists"
    echo "   📂 Contents:"
    ls -la "$REPO_PATH" | head -10
else
    echo "   ❌ Clone directory NOT found!"
    exit 1
fi
echo ""

# Step 4: Verify project has repo_url
REPO_URL=$(echo "$REPO_RESPONSE" | jq -r '.repo_url')
echo "4️⃣ Verifying stored repo_url: $REPO_URL"
if [ "$REPO_URL" == "https://github.com/anthropics/anthropic-sdk-python" ]; then
    echo "   ✅ repo_url correctly stored"
else
    echo "   ❌ repo_url mismatch!"
    exit 1
fi
echo ""

# Step 5: Test re-clone
echo "5️⃣ Testing re-clone (should delete and re-clone)..."
RECLONE_RESPONSE=$(curl -s -X POST "$API_URL/projects/$PROJECT_ID/add-repo" \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/anthropics/anthropic-sdk-python"}')

if [ -d "$REPO_PATH" ]; then
    echo "   ✅ Re-clone successful"
else
    echo "   ❌ Re-clone failed!"
    exit 1
fi
echo ""

# Step 6: List projects and verify repo_url is included
echo "6️⃣ Verifying repo_url in project list..."
LIST_RESPONSE=$(curl -s "$API_URL/projects")
HAS_REPO_URL=$(echo "$LIST_RESPONSE" | jq --arg id "$PROJECT_ID" '.[] | select(.id == $id) | .repo_url')

if [ -n "$HAS_REPO_URL" ]; then
    echo "   ✅ repo_url included in project list"
else
    echo "   ❌ repo_url missing from project list!"
    exit 1
fi
echo ""

echo "🎉 All tests passed!"
echo ""
echo "Cleanup: You can delete the test project and clone with:"
echo "  rm -rf $REPO_PATH"
echo "  curl -X DELETE $API_URL/projects/$PROJECT_ID"
