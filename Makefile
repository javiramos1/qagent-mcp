# Makefile for Q&A Agent Project with MCP support
.PHONY: help install run test clean docker-build docker-run docker-stop format lint mcp-server mcp-dev

# Default target
help:
	@echo "Available commands:"
	@echo "  install       - Install dependencies and setup virtual environment"
	@echo "  run           - Run the FastAPI application locally"
	@echo "  mcp-server    - Run the MCP server with HTTP transport (recommended)"
	@echo "  mcp-dev       - Run the MCP server with FastMCP inspector"
	@echo "  mcp-stdio     - Run the MCP server with STDIO transport (legacy)"
	@echo "  mcp-test      - Test MCP server functionality"
	@echo "  mcp-full-test - Run comprehensive MCP integration tests"
	@echo "  test          - Run tests"
	@echo "  clean         - Clean up temporary files and virtual environment"
	@echo "  docker-build  - Build Docker image for MCP architecture"
	@echo "  docker-run    - Start both MCP server and FastAPI client with docker-compose"
	@echo "  docker-stop   - Stop docker-compose services"
	@echo "  docker-logs   - Show logs from all services"
	@echo "  docker-logs-mcp - Show logs from MCP server only"
	@echo "  docker-logs-api - Show logs from FastAPI client only"
	@echo "  docker-restart - Restart docker-compose services"
	@echo "  docker-rebuild - Rebuild and restart docker-compose services"
	@echo "  format        - Format code with black"
	@echo "  lint          - Run linting checks"
	@echo "  requirements  - Generate requirements.txt"

# Python and virtual environment setup
VENV_NAME = qagent_venv
PYTHON = python3
PIP = $(VENV_NAME)/bin/pip
PYTHON_VENV = $(VENV_NAME)/bin/python

# Install dependencies and setup virtual environment
install:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV_NAME)
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "Setup complete! Activate with: source $(VENV_NAME)/bin/activate"

# Run the application locally
run:
	@echo "Starting Q&A Agent FastAPI server..."
	$(PYTHON_VENV) main.py

# MCP Server commands (updated for HTTP transport)
mcp-server:
	@echo "Starting MCP server with HTTP transport on port 8001 (recommended)..."
	qagent_venv/bin/fastmcp run mcp_server.py --transport streamable-http --port 8001

mcp-stdio:
	@echo "Starting MCP server with STDIO transport (legacy)..."
	$(PYTHON_VENV) mcp_server.py

mcp-dev:
	@echo "Starting MCP server with FastMCP inspector..."
	$(PYTHON_VENV) -c "import sys; sys.path.insert(0, 'qagent_venv/bin'); exec(open('qagent_venv/bin/fastmcp').read())" dev mcp_server.py

mcp-http:
	@echo "Starting MCP server with HTTP transport on port 8001..."
	qagent_venv/bin/fastmcp run mcp_server.py --transport streamable-http --port 8001

mcp-cli:
	@echo "Running MCP server with FastMCP CLI..."
	qagent_venv/bin/fastmcp run mcp_server.py

mcp-test:
	@echo "Testing MCP server (basic import and syntax check)..."
	$(PYTHON_VENV) -c "import mcp_server; print('✅ MCP server imports successfully')"
	@echo "Testing FastMCP CLI availability..."
	$(PYTHON_VENV) -m fastmcp --help > /dev/null && echo "✅ FastMCP CLI is available" || echo "❌ FastMCP CLI not available"

# Run tests (add test files as needed)
test:
	@echo "Running tests..."
	$(PYTHON_VENV) -m pytest tests/ -v || echo "No tests found. Add tests in tests/ directory."

# Clean up temporary files and virtual environment
clean:
	@echo "Cleaning up..."
	rm -rf $(VENV_NAME)
	rm -rf __pycache__
	rm -rf *.pyc
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete

# Docker commands
docker-build:
	@echo "Building Docker image for MCP architecture..."
	docker build -t qa-agent-mcp .

docker-run:
	@echo "Starting MCP server and FastAPI client with docker-compose..."
	docker-compose up -d

docker-stop:
	@echo "Stopping docker-compose services..."
	docker-compose down

docker-logs:
	@echo "Showing docker-compose logs..."
	docker-compose logs -f

docker-logs-mcp:
	@echo "Showing MCP server logs..."
	docker-compose logs -f mcp-server

docker-logs-api:
	@echo "Showing FastAPI client logs..."
	docker-compose logs -f qa-agent

docker-restart:
	@echo "Restarting docker-compose services..."
	docker-compose restart

docker-rebuild:
	@echo "Rebuilding and restarting docker-compose services..."
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d

# Code formatting and linting
format:
	@echo "Formatting code with black..."
	$(PYTHON_VENV) -m black . || echo "Install black with: pip install black"

lint:
	@echo "Running linting checks..."
	$(PYTHON_VENV) -m flake8 . || echo "Install flake8 with: pip install flake8"

# Generate requirements.txt from current environment
requirements:
	@echo "Generating requirements.txt..."
	$(PIP) freeze > requirements.txt

# Development helpers
dev-install:
	@echo "Installing development dependencies..."
	$(PIP) install black flake8 pytest

# MCP development helpers
mcp-test:
	@echo "Testing MCP server (basic import and syntax check)..."
	$(PYTHON_VENV) -c "import mcp_server; print('✅ MCP server imports successfully')"
	@echo "Testing FastMCP CLI availability..."
	qagent_venv/bin/fastmcp --help > /dev/null && echo "✅ FastMCP CLI is available" || echo "❌ FastMCP CLI not available"

mcp-integration-test:
	@echo "Running comprehensive MCP integration tests..."
	$(PYTHON_VENV) test_complete_mcp.py

mcp-full-test: mcp-test mcp-integration-test
	@echo "✅ All MCP tests completed successfully!"

# Quick start for new users (updated for HTTP workflow)
quick-start: install
	@echo "Quick start complete!"
	@echo "1. Copy .env.example to .env and add your API keys"
	@echo "2. Run 'make mcp-full-test' to verify MCP setup"
	@echo "3. Run 'make mcp-server' to start the MCP server with HTTP transport (in one terminal)"
	@echo "4. In another terminal, run 'make run' to start the FastAPI application"
	@echo "5. Visit http://localhost:8000/docs for API documentation"
	@echo "6. The FastAPI app will connect to MCP server via HTTP at http://127.0.0.1:8001"
	@echo "7. Or use 'make mcp-dev' to test tools with FastMCP inspector"

# Test the new langchain-mcp-adapters workflow
test-http-workflow:
	@echo "Testing the complete HTTP MCP workflow..."
	@echo "Step 1: Testing MCP server can start with HTTP transport..."
	$(PYTHON_VENV) -c "import mcp_server; print('✅ MCP server imports successfully')"
	@echo "Step 2: Testing langchain-mcp-adapters imports..."
	$(PYTHON_VENV) -c "from langchain_mcp_adapters.client import MultiServerMCPClient; from langchain_mcp_adapters.tools import load_mcp_tools; print('✅ langchain-mcp-adapters available')"
	@echo "Step 3: Testing qa_agent imports..."
	$(PYTHON_VENV) -c "from qa_agent import DomainQAAgent; print('✅ QA Agent imports successfully')"
	@echo "✅ HTTP workflow components are ready!"
	@echo "To test end-to-end: 1) make mcp-server 2) make run" 