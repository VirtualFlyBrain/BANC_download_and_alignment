#!/bin/bash

# Installation script for BANC coordinate transformation dependencies
# This script installs the official BANC transformation functions

echo "Setting up BANC coordinate transformation dependencies..."

# Check if Python virtual environment is active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Warning: No virtual environment detected. Consider activating a virtual environment first."
    echo "Example: python -m venv banc_env && source banc_env/bin/activate"
fi

# Install standard requirements first
echo "Installing standard requirements..."
pip install -r requirements.txt

# Install pytransformix (elastix wrapper)
echo "Installing pytransformix..."
pip install git+https://github.com/jasper-tms/pytransformix.git

# Clone and install BANC repository
echo "Cloning BANC repository..."
if [ -d "the-BANC-fly-connectome" ]; then
    echo "BANC repository already exists, updating..."
    cd the-BANC-fly-connectome
    git pull
    cd ..
else
    git clone https://github.com/jasper-tms/the-BANC-fly-connectome.git
fi

echo "Installing BANC package..."
cd the-BANC-fly-connectome
pip install -e .
cd ..

# Check elastix installation
echo "Checking elastix installation..."
if command -v elastix &> /dev/null; then
    echo "✓ Elastix found: $(which elastix)"
else
    echo "⚠️  Elastix not found in PATH!"
    echo "Please install elastix binary:"
    echo "  macOS: brew install elastix"
    echo "  Linux: apt-get install elastix or download from https://elastix.lumc.nl/"
    echo "  Windows: Download from https://elastix.lumc.nl/"
fi

# Test import
echo "Testing BANC transformation imports..."
python -c "
try:
    from fanc.transforms.template_alignment import warp_points_BANC_to_template
    print('✓ BANC transformation functions available')
except ImportError as e:
    print(f'✗ Import failed: {e}')
"

echo "Installation complete!"
echo ""
echo "To use BANC coordinate transformations:"
echo "1. Ensure elastix is installed and in PATH"
echo "2. Run the pipeline with: python run_banc_pipeline.py <neuron_id>"
echo "3. Coordinates will be automatically transformed from BANC to JRC2018F/VNC templates"
