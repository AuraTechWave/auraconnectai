#!/bin/bash

# AuraConnect AI - Kubernetes Secrets Management Script
# This script helps manage secrets for different environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
NAMESPACE="auraconnect"
ENVIRONMENT=""
SECRET_NAME="auraconnect-secrets"

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment (development, staging, production)"
    echo "  -n, --namespace NS       Kubernetes namespace (default: auraconnect)"
    echo "  -f, --file FILE         Path to .env file with secrets"
    echo "  -g, --generate          Generate template .env file"
    echo "  -a, --apply             Apply secrets to Kubernetes"
    echo "  -d, --delete            Delete existing secrets"
    echo "  -v, --verify            Verify secrets are loaded"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -g                   Generate template .env file"
    echo "  $0 -e production -f .env.prod -a    Apply production secrets"
    echo "  $0 -e staging -v        Verify staging secrets"
}

# Function to generate template .env file
generate_template() {
    local env_file="${1:-.env.secrets}"
    
    cat > "$env_file" << 'EOF'
# Database Credentials
POSTGRES_PASSWORD=your-secure-password-here
DATABASE_URL=postgresql://auraconnect:your-secure-password-here@postgres:5432/auraconnect

# Redis Credentials
REDIS_PASSWORD=your-redis-password-here
REDIS_URL=redis://default:your-redis-password-here@redis:6379/0

# JWT Secret
JWT_SECRET_KEY=your-very-long-random-secret-key-here

# Payment Gateway Credentials
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
SQUARE_ACCESS_TOKEN=EAAAE...
SQUARE_LOCATION_ID=L...
PAYPAL_CLIENT_ID=AV...
PAYPAL_CLIENT_SECRET=EK...

# Email Credentials
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password

# SMS Credentials (Twilio)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# Push Notifications (Firebase)
FIREBASE_CREDENTIALS={"type":"service_account","project_id":"..."}

# AWS Credentials
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=auraconnect-uploads

# Monitoring
SENTRY_DSN=https://...@sentry.io/...

# Frontend Secrets
REACT_APP_GOOGLE_MAPS_API_KEY=AIza...
REACT_APP_STRIPE_PUBLISHABLE_KEY=pk_live_...
REACT_APP_SENTRY_DSN=https://...@sentry.io/...
EOF
    
    print_message "$GREEN" "✓ Template generated: $env_file"
    print_message "$YELLOW" "⚠ Edit this file with your actual secrets before applying"
}

# Function to create Kubernetes secret from .env file
create_secret_from_env() {
    local env_file=$1
    
    if [ ! -f "$env_file" ]; then
        print_message "$RED" "✗ File not found: $env_file"
        exit 1
    fi
    
    # Check if secret exists
    if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
        print_message "$YELLOW" "⚠ Secret $SECRET_NAME already exists in namespace $NAMESPACE"
        read -p "Do you want to delete and recreate it? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE"
            print_message "$GREEN" "✓ Existing secret deleted"
        else
            print_message "$RED" "✗ Operation cancelled"
            exit 1
        fi
    fi
    
    # Create the secret
    kubectl create secret generic "$SECRET_NAME" \
        --from-env-file="$env_file" \
        --namespace="$NAMESPACE"
    
    print_message "$GREEN" "✓ Secret $SECRET_NAME created in namespace $NAMESPACE"
}

# Function to verify secrets
verify_secrets() {
    print_message "$YELLOW" "Verifying secrets in namespace: $NAMESPACE"
    
    if ! kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
        print_message "$RED" "✗ Secret $SECRET_NAME not found in namespace $NAMESPACE"
        exit 1
    fi
    
    # Get secret keys
    local keys=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data}' | jq -r 'keys[]')
    
    print_message "$GREEN" "✓ Secret $SECRET_NAME found with the following keys:"
    for key in $keys; do
        echo "  - $key"
    done
    
    # Check if all required keys are present
    local required_keys=(
        "POSTGRES_PASSWORD"
        "DATABASE_URL"
        "REDIS_PASSWORD"
        "REDIS_URL"
        "JWT_SECRET_KEY"
    )
    
    local missing_keys=()
    for key in "${required_keys[@]}"; do
        if ! echo "$keys" | grep -q "^$key$"; then
            missing_keys+=("$key")
        fi
    done
    
    if [ ${#missing_keys[@]} -gt 0 ]; then
        print_message "$RED" "✗ Missing required keys:"
        for key in "${missing_keys[@]}"; do
            echo "  - $key"
        done
        exit 1
    else
        print_message "$GREEN" "✓ All required keys are present"
    fi
}

# Function to delete secrets
delete_secrets() {
    if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
        kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE"
        print_message "$GREEN" "✓ Secret $SECRET_NAME deleted from namespace $NAMESPACE"
    else
        print_message "$YELLOW" "⚠ Secret $SECRET_NAME not found in namespace $NAMESPACE"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -f|--file)
            ENV_FILE="$2"
            shift 2
            ;;
        -g|--generate)
            GENERATE=true
            shift
            ;;
        -a|--apply)
            APPLY=true
            shift
            ;;
        -d|--delete)
            DELETE=true
            shift
            ;;
        -v|--verify)
            VERIFY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_message "$RED" "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Set namespace based on environment if specified
if [ -n "$ENVIRONMENT" ]; then
    case $ENVIRONMENT in
        development|dev)
            NAMESPACE="${NAMESPACE}-dev"
            SECRET_NAME="${SECRET_NAME}-dev"
            ;;
        staging|stage)
            NAMESPACE="${NAMESPACE}-staging"
            SECRET_NAME="${SECRET_NAME}-staging"
            ;;
        production|prod)
            NAMESPACE="${NAMESPACE}"
            SECRET_NAME="${SECRET_NAME}"
            ;;
        *)
            print_message "$RED" "Invalid environment: $ENVIRONMENT"
            exit 1
            ;;
    esac
fi

# Execute requested actions
if [ "$GENERATE" = true ]; then
    generate_template "${ENV_FILE:-.env.secrets}"
elif [ "$APPLY" = true ]; then
    if [ -z "$ENV_FILE" ]; then
        print_message "$RED" "✗ Please specify an env file with -f option"
        exit 1
    fi
    create_secret_from_env "$ENV_FILE"
elif [ "$DELETE" = true ]; then
    delete_secrets
elif [ "$VERIFY" = true ]; then
    verify_secrets
else
    usage
    exit 0
fi