#!/bin/bash
set -e

# =============================================================================
# AWS What's New Alerts - Full Deployment Script
# =============================================================================
# This script deploys the complete stack:
#   1. CDK Infrastructure (SNS, Memory, Cognito, S3, CloudFront)
#   2. Agent Configuration (Secrets Manager)
#   3. Agent Runtime (AgentCore)
#   4. Frontend (S3 + CloudFront)
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

Deploy the AWS What's New Alerts system.

OPTIONS:
    -e, --email EMAIL       Email address for newsletter subscription (required)
    -r, --region REGION     AWS region (default: us-west-2)
    -s, --stack-name NAME   CloudFormation stack name (default: aws-newsletter-prod)
    -h, --help              Show this help message

EXAMPLES:
    $0 --email your-email@example.com
    $0 --email your-email@example.com --region us-east-1
    $0 -e your-email@example.com -r us-west-2 -s my-newsletter-stack

PREREQUISITES:
    - AWS CLI configured with appropriate credentials
    - AWS CDK CLI installed (npm install -g aws-cdk)
    - Python 3.10+ with virtual environment
    - agentcore CLI installed (pip install bedrock-agentcore-cli)

EOF
    exit 0
}

# Parse command line arguments
EMAIL=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--email)
            EMAIL="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
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

# Validate required arguments
if [ -z "$EMAIL" ]; then
    print_error "Email address is required"
    echo "Usage: $0 --email your-email@example.com"
    exit 1
fi

# Validate email format
if [[ ! "$EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
    print_error "Invalid email format: $EMAIL"
    exit 1
fi

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."

    local missing=()

    if ! command -v aws &> /dev/null; then
        missing+=("aws CLI")
    fi

    if ! command -v cdk &> /dev/null; then
        missing+=("AWS CDK CLI (npm install -g aws-cdk)")
    fi

    if ! command -v python3 &> /dev/null; then
        missing+=("Python 3")
    fi

    if ! command -v agentcore &> /dev/null; then
        missing+=("agentcore CLI (pip install bedrock-agentcore-cli)")
    fi

    if [ ${#missing[@]} -ne 0 ]; then
        print_error "Missing prerequisites:"
        for item in "${missing[@]}"; do
            echo "  - $item"
        done
        exit 1
    fi

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi

    echo "All prerequisites met."
}

# Activate virtual environment
activate_venv() {
    if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
        source "$SCRIPT_DIR/.venv/bin/activate"
    else
        print_warning "Virtual environment not found at $SCRIPT_DIR/.venv"
        print_warning "Creating virtual environment..."
        python3 -m venv "$SCRIPT_DIR/.venv"
        source "$SCRIPT_DIR/.venv/bin/activate"
        pip install -r "$SCRIPT_DIR/requirements.txt"
        pip install -r "$SCRIPT_DIR/backend/requirements.txt"
        pip install -r "$SCRIPT_DIR/agent/requirements.txt"
    fi
}

# Step 1: Deploy CDK Infrastructure
deploy_infrastructure() {
    print_step "Step 1/4: Deploying CDK Infrastructure..."

    cd "$SCRIPT_DIR/backend"

    # Check if CDK is bootstrapped
    if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" &> /dev/null; then
        print_warning "CDK not bootstrapped. Running cdk bootstrap..."
        cdk bootstrap "aws://$(aws sts get-caller-identity --query Account --output text)/$REGION"
    fi

    # Deploy the stack
    cdk deploy --context email="$EMAIL" --require-approval never

    echo "Infrastructure deployed successfully."
}

# Step 2: Configure Secrets
configure_secrets() {
    print_step "Step 2/4: Configuring Secrets..."

    cd "$SCRIPT_DIR/backend"
    python configure_secret.py --stack-name "$STACK_NAME" --region "$REGION" --email "$EMAIL"

    echo "Secrets configured successfully."
}

# Step 3: Deploy Agent
deploy_agent() {
    print_step "Step 3/4: Deploying Agent..."

    cd "$SCRIPT_DIR/agent"

    # Source the generated config
    if [ -f "agent_config.env" ]; then
        source agent_config.env
    else
        print_error "agent_config.env not found. Run configure_secret.py first."
        exit 1
    fi

    # Configure the agent with JWT authorization for per-user memory isolation
    # The AUTHORIZER_CONFIG enables AgentCore to validate Cognito JWTs
    # and pass the user identity (sub claim) to the agent via headers
    echo "Configuring agent with JWT authorization..."
    if [ -n "$AUTHORIZER_CONFIG" ]; then
        agentcore configure -e agent.py \
            --region "$REGION" \
            --name "$AGENT_NAME" \
            --execution-role "$AGENTCORE_RUNTIME_ROLE_ARN" \
            --authorizer-config "$AUTHORIZER_CONFIG" \
            --request-header-allowlist "Authorization"
    else
        echo "Warning: AUTHORIZER_CONFIG not set. Deploying without JWT auth."
        agentcore configure -e agent.py \
            --region "$REGION" \
            --name "$AGENT_NAME" \
            --execution-role "$AGENTCORE_RUNTIME_ROLE_ARN"
    fi

    # Launch the agent
    echo "Launching agent..."
    agentcore launch --env SECRET_NAME="$SECRET_NAME" --env AWS_REGION="$REGION"

    echo "Agent deployed successfully."
}

# Step 4: Deploy Frontend
deploy_frontend() {
    print_step "Step 4/4: Deploying Frontend..."

    cd "$SCRIPT_DIR/backend"
    python deploy_frontend.py

    echo "Frontend deployed successfully."
}

# Main execution
main() {
    echo "=============================================="
    echo "  AWS What's New Alerts - Full Deployment"
    echo "=============================================="
    echo "Email:      $EMAIL"
    echo "Region:     $REGION"
    echo "Stack:      $STACK_NAME"
    echo "=============================================="

    check_prerequisites
    activate_venv

    deploy_infrastructure
    configure_secrets
    deploy_agent
    deploy_frontend

    echo ""
    echo "=============================================="
    echo -e "${GREEN}Deployment Complete!${NC}"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo "  1. Check your email ($EMAIL) to confirm SNS subscription"
    echo "  2. Visit the CloudFront URL printed above to access the Chat UI"
    echo "  3. Ask the agent to 'Set up daily newsletter delivery at 8 AM'"
    echo ""
}

main
