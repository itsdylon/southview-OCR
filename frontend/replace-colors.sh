#!/bin/bash

# Replace all indigo- with blue- in TypeScript React files
find /src/app -name "*.tsx" -type f 2>/dev/null | while read file; do
  sed -i 's/indigo-/blue-/g' "$file" 2>/dev/null || true
done

echo "Replaced all indigo- with blue- in .tsx files"
