#!/bin/bash
# Skript pro kopírování konkrétních souborů do Mylar kontejneru
# Použití: ./copy_files_to_mylar.sh "file1,file2,file3"

set -e

# Najdeme Mylar kontejner
CONTAINER=$(docker ps --filter 'name=mylar' --format '{{.Names}}' | head -n 1)

if [ -z "$CONTAINER" ]; then
    echo "❌ Mylar container not found!"
    echo "💡 Running containers:"
    docker ps --format "  {{.Names}}"
    exit 1
fi

echo "📦 Copying files to container: $CONTAINER"

# Získáme seznam souborů z parametru
FILES_LIST="$1"

if [ -z "$FILES_LIST" ]; then
    echo "❌ No files specified!"
    exit 1
fi

# Rozdělíme soubory podle čárek a zkopírujeme
echo "$FILES_LIST" | tr ',' '\n' | while read -r file; do
    # Odstraníme mezery
    file=$(echo "$file" | xargs)
    
    if [ -z "$file" ]; then
        continue
    fi
    
    if [ -f "$file" ]; then
        echo "Copying $file..."
        if docker cp "$file" "$CONTAINER:/app/mylar/$file"; then
            echo "✅ $file copied"
        else
            echo "⚠️  Failed to copy $file"
            exit 1
        fi
    else
        echo "⚠️  File not found: $file"
    fi
done

echo "✅ Done!"
