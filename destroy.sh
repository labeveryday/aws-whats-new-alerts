#!/bin/bash
set -e

# =============================================================================
# AWS What's New Alerts - Full Destroy Script
# =============================================================================
# This script destroys the complete stack in reverse order:
#   1. Agent Runtime (AgentCore)
#   2. CDK Infrastructure (SNS, Memory, Cognito, S3, CloudFront)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_REGION:-us-west-2}"
STACK_NAME="${STACK_NAME:-aws-newsletter-prod}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "\n${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

print_error() {
    echo -e "${RED}Error:${NC} $1"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Destroy the AWS What's New Alerts system.

OPTIONS:
    -r, --region REGION     AWS region (default: us-west-2)
    -s, --stack-name NAME   CloudFormation stack name (default: aws-newsletter-prod)
    -y, --yes               Skip confirmation prompt
    -h, --help              Show this help message

EXAMPLES:
    $0
    $0 --region us-east-1
    $0 -s my-newsletter-stack -y

EOF
    exit 0
}

# Parse command line arguments
SKIP_CONFIRM=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -y|--yes)
            SKIP_CONFIRM="true"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Activate virtual environment
activate_venv() {
    if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
        source "$SCRIPT_DIR/.venv/bin/activate"
    fi
}

# Step 1: Destroy Agent
destroy_agent() {
    print_step "Step 1/2: Destroying Agent..."

    cd "$SCRIPT_DIR/agent"

    # Check if agent is configured
    if [ -f ".bedrock_agentcore.yaml" ]; then
        echo "Destroying agent runtime..."
        agentcore destroy --force || print_warning "Agent destroy failed (may not exist)"
    else
        print_warning "No agent configuration found. Skipping agent destroy."
    fi

    echo "Agent destroyed."
}

# Step 2: Destroy CDK Infrastructure
destroy_infrastructure() {
    print_step "Step 2/2: Destroying CDK Infrastructure..."

    cd "$SCRIPT_DIR/backend"

    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" &> /dev/null; then
        echo "Destroying CloudFormation stack: $STACK_NAME"
        cdk destroy --force
    else
        print_warning "Stack $STACK_NAME not found in region $REGION. Skipping CDK destroy."
    fi

    echo "Infrastructure destroyed."
}

# Main execution
main() {
    echo "=============================================="
    echo "  AWS What's New Alerts - Full Destroy"
    echo "=============================================="
    echo "Region:     $REGION"
    echo "Stack:      $STACK_NAME"
    echo "=============================================="

    if [ -z "$SKIP_CONFIRM" ]; then
        echo ""
        echo -e "${RED}WARNING: This will permanently delete all resources!${NC}"
        echo "  - AgentCore Runtime"
        echo "  - SNS Topic and Subscriptions"
        echo "  - AgentCore Memory"
        echo "  - Cognito User/Identity Pools"
        echo "  - S3 Bucket (frontend)"
        echo "  - CloudFront Distribution"
        echo "  - Secrets Manager Secret"
        echo "  - IAM Roles"
        echo ""
        read -p "Are you sure you want to continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 0
        fi
    fi

    activate_venv

    destroy_agent
    destroy_infrastructure

    echo ""
    echo "=============================================="
    echo -e "${GREEN}Destroy Complete!${NC}"
    echo "=============================================="
    echo ""
    echo "All resources have been deleted."
    echo ""
}

main
