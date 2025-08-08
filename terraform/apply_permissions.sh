#!/bin/bash
# run ./terraform/apply_permissions.sh to apply any terraform changes

echo "🔧 Applying Terraform changes..."

# Navigate to terraform directory
cd "$(dirname "$0")"

# Initialize Terraform (if not already done)
echo "📦 Initializing Terraform..."
terraform init

# Validate the configuration
echo "✅ Validating Terraform configuration..."
terraform validate

# Plan the changes
echo "📋 Planning Terraform changes..."
terraform plan

# Apply the changes
echo "🚀 Applying Terraform changes..."
terraform apply -auto-approve

echo "✅ Done! Terraform changes applied."

