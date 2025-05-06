#!/bin/bash

# Exit on error
set -e

echo "Packaging Lambda function..."

# Create temporary directory for packaging
rm -rf temp_package
mkdir -p temp_package/src

# Copy source code preserving package structure
cp -r src/* temp_package/src/

# Install dependencies
pip install --quiet -r requirements.txt --target temp_package

# Remove unnecessary files
find temp_package -type d -name "__pycache__" -exec rm -rf {} +
find temp_package -type f -name "*.pyc" -delete
find temp_package -type f -name "*.pyo" -delete
find temp_package -type f -name "*.pyd" -delete
find temp_package -type d -name "tests" -exec rm -rf {} +
find temp_package -type d -name "test" -exec rm -rf {} +

# Create deployment package
cd temp_package
zip -r ../src.zip .
cd ..

# Clean up
rm -rf temp_package

echo "Lambda package created successfully as src.zip"