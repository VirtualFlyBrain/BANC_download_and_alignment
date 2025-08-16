# BANC → VFB Processing Pipeline

Complete pipeline for downloading BANC connectome neuron data and converting it to VFB-compatible formats with proper coordinate transformations.

## Overview

This pipeline processes neurons from the BANC (Brain and Nerve Cord) fly connectome dataset and prepares them for integration with the Virtual Fly Brain (VFB) knowledge base. It handles:

- ✅ **Data Access**: Downloads from BANC public data bucket
- ✅ **Coordinate Transformation**: Official BANC→JRC2018F/VNC transforms  
- ✅ **Multi-format Output**: SWC, OBJ mesh, NRRD volume formats
- ✅ **VFB Integration**: Compatible with VFB metadata and templates

## Quick Start

### Jenkins Production Command

For production deployment in Jenkins:

```bash
# Install dependencies
./install_banc_transforms.sh

# Process single neuron with all formats
python run_banc_pipeline.py 648518346349541188 --formats swc,obj,nrrd

# Process batch of neurons
python run_banc_pipeline.py 648518346349541188,648518346349541189 --formats swc,obj,nrrd
```

### Installation

1. **Clone and Setup**:
```bash
git clone <this-repository>
cd BANC_download_and_alignment
python -m venv banc_env
source banc_env/bin/activate  # On Windows: banc_env\Scripts\activate
```

2. **Install Dependencies**:
```bash
./install_banc_transforms.sh
```

This will install:
- Standard Python packages (navis, pandas, etc.)
- BANC transformation functions
- Google Cloud SDK for data access
- ElastiX for coordinate transformations

## Architecture

### Data Flow

```
VFB Neo4j DB → BANC Public Bucket → Coordinate Transform → Multi-format Output
     ↓                ↓                      ↓                     ↓
   Metadata        SWC Files           JRC2018F/VNC         SWC, OBJ, NRRD
```

### Key Components

1. **`process.py`**: Core processing functions
   - `get_banc_626_skeleton()`: Downloads from public bucket
   - `transform_skeleton_coordinates()`: Official BANC transforms
   - `process_vfb_neuron_with_banc_data()`: End-to-end workflow

2. **`run_banc_pipeline.py`**: Command-line interface
   - Multi-format processing
   - Error handling and logging
   - Production-ready deployment

3. **Coordinate Transformations**: 
   - Automatic brain/VNC detection
   - BANC → JRC2018F (brain) or JRCVNC2018F (VNC)
   - Optional chaining to JRC2018U for VFB compatibility

## Usage

### Basic Processing

```bash
# Single neuron, SWC format only
python run_banc_pipeline.py 648518346349541188

# Multiple formats
python run_banc_pipeline.py 648518346349541188 --formats swc,obj,nrrd

# Batch processing
python run_banc_pipeline.py 648518346349541188,648518346349541189,648518346349541190
```

### Advanced Options

```bash
# Custom output directory
python run_banc_pipeline.py 648518346349541188 --output-dir /path/to/output

# Skip coordinate transformation (keep BANC coordinates)
python run_banc_pipeline.py 648518346349541188 --no-transform

# Verbose logging
python run_banc_pipeline.py 648518346349541188 --verbose
```

## Output Formats

### SWC (Skeleton)
- Standard neuroanatomy format
- Point-based tree structure
- Compatible with all neuron visualization tools

### OBJ (Mesh)
- 3D surface mesh representation
- Generated using navis mesh conversion
- Suitable for 3D rendering and analysis

### NRRD (Volume)
- 3D volumetric representation
- Rasterized skeleton with configurable radius
- Compatible with medical imaging tools

## Coordinate Transformations

The pipeline uses official BANC transformation functions:

### Automatic Region Detection
- **Brain neurons** (y < 320,000 nm): → JRC2018F template
- **VNC neurons** (y ≥ 320,000 nm): → JRCVNC2018F template

### Transform Chain
```
BANC coordinates → JRC2018F/VNC → (optional) JRC2018U
```

### Dependencies
- **BANC package**: Official transformation functions
- **pytransformix**: ElastiX Python wrapper  
- **ElastiX binary**: Core transformation engine

## Configuration

### VFB Database Connection

Edit connection details in `process.py`:
```python
def get_vfb_neuron_metadata(neuron_id):
    driver = GraphDatabase.driver(
        "bolt://kbw.virtualflybrain.org:7474",
        auth=("neo4j", "vfb")
    )
```

### BANC Data Access

Uses Google Cloud public bucket (no authentication required):
```python
BANC_BUCKET = "gs://lee-lab_brain-and-nerve-cord-fly-connectome"
```

## Troubleshooting

### Common Issues

1. **Import Error: fanc.transforms**
   ```bash
   # Install BANC package
   ./install_banc_transforms.sh
   ```

2. **ElastiX not found**
   ```bash
   # macOS
   brew install elastix
   
   # Linux
   apt-get install elastix
   
   # Or download from https://elastix.lumc.nl/
   ```

3. **Google Cloud SDK**
   ```bash
   # Install gsutil
   pip install google-cloud-storage
   gcloud auth application-default login  # Optional for private buckets
   ```

### Error Logs

The pipeline provides detailed error logging:
- Network connectivity issues
- Missing dependencies
- Coordinate transformation failures
- File I/O problems

All errors include fallback behaviors to ensure processing continues.

## Development

### Testing

```bash
# Test with public BANC data
python test_banc_public_data.py

# Test coordinate transformations
python -c "
from process import transform_skeleton_coordinates
# Test code here
"
```

### Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit pull request

## Data Sources

- **BANC Connectome**: Jasper et al., Nature 2023
- **Public Data**: `gs://lee-lab_brain-and-nerve-cord-fly-connectome/`
- **VFB Database**: Virtual Fly Brain knowledge base
- **Templates**: JRC2018F, JRCVNC2018F, JRC2018U

## License

[Specify license - typically matches source data licensing]

## Citation

If using this pipeline, please cite:
- BANC paper: [Jasper et al., Nature 2023]
- VFB: [Virtual Fly Brain project]
- navis: [Schlegel et al., 2022]
