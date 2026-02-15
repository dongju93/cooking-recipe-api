#!/bin/bash
# Linting, formatting, and type checking script for cooking-recipe-api

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_step() {
    echo -e "${GREEN}==>${NC} $1"
}

print_error() {
    echo -e "${RED}Error:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}Warning:${NC} $1"
}

# Function to run ruff format
format() {
    print_step "Running ruff format..."
    uv run ruff format src/
    echo -e "${GREEN}✓${NC} Formatting complete"
}

# Function to run type checking
check() {
    print_step "Running pyrefly type checking..."
    uv run pyrefly check src/
    echo -e "${GREEN}✓${NC} Type checking complete"
}

# Function to run linting
lint() {
    print_step "Running ruff linting..."
    uv run ruff check --fix src/
    echo -e "${GREEN}✓${NC} Linting complete"
}

# Function to run all checks
all() {
    print_step "Running all code quality checks..."
    format
    lint
    check
    echo -e "\n${GREEN}✓${NC} All checks passed!"
}

# Main script logic
case "${1:-all}" in
    format)
        format
        ;;
    check)
        check
        ;;
    lint)
        lint
        ;;
    all)
        all
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Usage: $0 {format|check|lint|all}"
        echo ""
        echo "Commands:"
        echo "  format  - Format code using ruff"
        echo "  check   - Run type checking using pyrefly"
        echo "  lint    - Run linting using ruff (with auto-fix)"
        echo "  all     - Run all checks (default)"
        exit 1
        ;;
esac
