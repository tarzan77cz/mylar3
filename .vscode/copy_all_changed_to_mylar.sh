#!/bin/bash
# Skript pro kopírování všech změněných souborů do Mylar kontejneru

set -e

# Najdeme Mylar kontejner
CONTAINER=$(docker ps --filter 'name=mylar' --format '{{.Names}}' | head -n 1)

if [ -z "$CONTAINER" ]; then
    echo "❌ Mylar container not found!"
    echo "💡 Running containers:"
    docker ps --format "  {{.Names}}"
    exit 1
fi

echo "📦 Copying all changed files to container: $CONTAINER"

# Získáme seznam změněných souborů z gitu
CHANGED_FILES=$(git diff --name-only HEAD | grep -v '^\.vscode/' || true)

if [ -z "$CHANGED_FILES" ]; then
    echo "ℹ️  No changed files found"
    exit 0
fi

# Zkopírujeme každý soubor
echo "$CHANGED_FILES" | while read -r file; do
    if [ -z "$file" ]; then
        continue
    fi
    
    # Zkontrolujeme, jestli soubor není v .gitignore
    if git check-ignore -q "$file"; then
        echo "⏭️  Skipping $file (ignored by .gitignore)"
        continue
    fi
    
    if [ -f "$file" ]; then
        echo "Copying $file..."
        if docker cp "$file" "$CONTAINER:/app/mylar/$file" 2>/dev/null; then
            echo "✅ $file copied"
        else
            echo "⚠️  Failed to copy $file"
        fi
    else
        echo "⏭️  Skipping $file (not found)"
    fi
done

echo "✅ Done!"
