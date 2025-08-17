# BANC Data Processing Pipeline

## Overview

This repository contains the production pipeline for processing BANC (Brain and Nerve Cord) fly connectome data for integration with Virtual Fly Brain (VFB). The pipeline downloads high-quality neuron data from the public BANC dataset, transforms coordinates to appropriate template spaces, and generates standardized file formats for VFB.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Basic usage - process a few neurons for testing
python run_full_banc_production.py --limit 10 --dry-run

# Production usage - process all neurons
python run_full_banc_production.py --formats swc,obj,nrrd
```

## Features

- **Automated BANC Data Processing**: Downloads skeleton and mesh data from public BANC Google Cloud Storage
- **High-Quality Mesh Generation**: Uses actual BANC precomputed meshes (not skeleton-based approximations)
- **Dual Template Support**: Handles both brain (JRC2018U) and VNC (JRCVNC2018U) template spaces
- **BANC-Specific Transformations**: Uses official BANC coordinate transformation functions
- **Two-Step Alignment Pipeline**: BANC → intermediate template → final template space
- **Multiple Output Formats**: Generates SWC, OBJ, and NRRD files with proper metadata
- **VFB Database Integration**: Queries VFB Neo4j database for neuron organization and template mapping
- **Template-Aware Processing**: Automatically routes neurons to brain vs VNC transformation pipelines

## Pipeline Architecture

```text
VFB Database → BANC Public Data → Two-Step Transform → VFB File Structure
     ↓              ↓                    ↓                    ↓
  Template IDs   Skeleton/Mesh    BANC→JRC2018F/VNC→U     volume.[swc|obj|nrrd]
```

### Transformation Pipeline

**Brain Neurons (VFB_00101567):**
```text
BANC (nm) → [BANC transforms] → JRC2018F (µm) → [navis] → JRC2018U (µm)
```

**VNC Neurons (VFB_00200000):**
```text
BANC (nm) → [BANC transforms] → JRCVNC2018F (µm) → [navis] → JRCVNC2018U (µm)
```

## Output Structure

The pipeline creates files in VFB-standard folder organization with template-specific routing:

```text
vfb_banc_data/
├── processing_state.json
└── VFB/
    └── i/
        ├── 0010/
        │   └── 5bke/
        │       └── VFB_00101567/    # Brain template (JRC2018U)
        │           ├── volume.swc   # Transformed skeleton (4KB)
        │           ├── volume.obj   # High-quality mesh (6MB, 74K+ vertices)
        │           └── volume.nrrd  # Voxelized volume (0.622µm, wider > taller)
        └── 0020/
            └── 0000/
                └── VFB_00200000/    # VNC template (JRCVNC2018U)
                    ├── volume.swc   # Transformed skeleton
                    ├── volume.obj   # High-quality mesh  
                    └── volume.nrrd  # Voxelized volume (0.4µm, taller > wider)
```
            │       └── volume.nrrd  # Volumetric data (224KB, 0.622µm voxels)
            └── 5bkf/
                └── VFB_00101567/
                    ├── volume.swc
                    ├── volume.obj
                    └── volume.nrrd
```

## File Formats

### SWC Files (`volume.swc`)

- **Source**: BANC public skeleton data
- **Processing**: Coordinate transformation to template space
- **Format**: Standard SWC with micrometers units
- **Size**: ~4KB per neuron

### OBJ Files (`volume.obj`)

- **Source**: BANC precomputed mesh fragments (JSON + binary)
- **Processing**: Binary mesh parsing, coordinate transformation, OBJ generation
- **Quality**: High-detail meshes (70K+ vertices, 150K+ faces)
- **Size**: 5-10MB per neuron

### NRRD Files (`volume.nrrd`)

- **Source**: Generated from transformed OBJ meshes
- **Processing**: Mesh voxelization with template-specific metadata
- **Voxel Size**: 0.622µm (JRC2018U) or 0.4µm (JRCVNC2018U)
- **Size**: 200-500KB per neuron

## Usage

### Basic Usage

```bash
# Process all BANC neurons (production)
python run_full_banc_production.py

# Test with limited neurons
python run_full_banc_production.py --limit 10 --dry-run

# Specific formats only
python run_full_banc_production.py --formats swc,obj

# Custom output directory
python run_full_banc_production.py --output-dir /path/to/output
```

### Command Line Options

- `--output-dir`: Output directory (default: `vfb_banc_data`)
- `--formats`: Comma-separated formats (`swc,obj,nrrd`)
- `--limit`: Limit number of neurons for testing
- `--max-workers`: Parallel processing workers (default: 1)
- `--dry-run`: Show what would be processed without doing it
- `--no-skip-existing`: Reprocess existing files
- `--resume`: Resume from previous run (default behavior)

### Environment Configuration

For production deployment, set the data folder environment variable:

```bash
# Local development (default - uses current directory)
python run_full_banc_production.py --limit 5

# Production deployment (Jenkins)
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --formats swc,obj,nrrd
```

See [ENVIRONMENT_CONFIG.md](ENVIRONMENT_CONFIG.md) for detailed environment setup.
## Installation

### Prerequisites

1. **Python Environment**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Google Cloud SDK** (for BANC data access):
   ```bash
   # macOS
   brew install google-cloud-sdk
   
   # Linux
   apt-get install google-cloud-sdk
   ```

3. **BANC Transformation Tools** (Required for coordinate alignment):
   ```bash
   # Automated installation
   bash install_banc_transforms.sh
   
   # Or manual installation:
   git clone https://github.com/jasper-tms/the-BANC-fly-connectome.git
   cd the-BANC-fly-connectome && pip install -e .
   pip install git+https://github.com/jasper-tms/pytransformix.git
   
   # Install elastix (macOS)
   brew install elastix
   ```

## Key Dependencies

- `navis[all]`: Neuron analysis and visualization
- `vfb_connect`: VFB database connectivity  
- `pynrrd`: NRRD file format support
- `flybrains`: Template brain registration
- `pandas`, `numpy`: Data processing

## Monitoring and Logging

The pipeline provides comprehensive logging with progress indicators:

```text
2025-08-17 16:07:52,466 - INFO - 🧠 Processing BANC neuron: 720575941559970319
2025-08-17 16:07:52,466 - INFO -   📁 VFB folder: VFB_00101567 → JRC2018U
2025-08-17 16:07:54,377 - INFO -     ✅ SWC: volume.swc
2025-08-17 16:07:58,471 - INFO -     ✅ OBJ (BANC mesh): volume.obj
2025-08-17 16:08:03,910 - INFO -     ✅ NRRD (from mesh): volume.nrrd
```

Log files are written to `banc_production.log` in the working directory.

## Documentation

- **[Environment Configuration](ENVIRONMENT_CONFIG.md)**: Environment setup and deployment configuration
- **[Technical Details](TECHNICAL_DETAILS.md)**: Detailed technical specifications and architecture
- **[License](LICENSE)**: License information

## Quality Metrics

Recent processing results:
- **Mesh Quality**: 70K+ vertices, 150K+ triangles per neuron
- **File Sizes**: SWC (4KB), OBJ (6MB), NRRD (224KB)  
- **Processing Speed**: ~15 seconds per neuron
- **Success Rate**: 100% with fallback mechanisms

## Contributing

This pipeline is part of the VFB production infrastructure. For modifications:

1. Test with `--limit` and `--dry-run` options
2. Validate output file formats and coordinate spaces
3. Ensure VFB folder organization compliance
4. Update documentation for any new features

## License

See [LICENSE](LICENSE) file for details.
