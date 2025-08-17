# BANC Production Pipeline

## Overview

This repository contains the complete production pipeline for processing BANC (Brain and Nerve Cord) fly connectome data for integration with Virtual Fly Brain (VFB). The pipeline downloads high-quality neuron data from the public BANC dataset, transforms coordinates to appropriate template spaces, and generates standardized file formats for VFB.

## Features

- **Automated BANC Data Processing**: Downloads skeleton and mesh data from public BANC Google Cloud Storage
- **High-Quality Mesh Generation**: Uses actual BANC precomputed meshes (not skeleton-based approximations)
- **Coordinate Transformation**: Transforms from BANC space to JRC2018U/JRCVNC2018U template spaces
- **Multiple Output Formats**: Generates SWC, OBJ, and NRRD files with proper metadata
- **VFB Database Integration**: Queries VFB Neo4j database for neuron organization and template mapping
- **Template-Aware Processing**: Automatically selects appropriate template spaces (brain vs VNC)

## Pipeline Architecture

```text
VFB Database → BANC Public Data → Coordinate Transform → VFB File Structure
     ↓              ↓                    ↓                    ↓
  Neuron IDs    Skeleton/Mesh     JRC2018U/VNC Space    volume.[swc|obj|nrrd]
```

## Output Structure

The pipeline creates files in VFB-standard folder organization:

```text
vfb_banc_data/
├── processing_state.json
└── VFB/
    └── i/
        └── 0010/
            ├── 5bke/
            │   └── VFB_00101567/    # JRC2018U template
            │       ├── volume.swc   # Transformed skeleton (4KB)
            │       ├── volume.obj   # High-quality mesh (6MB, 74K+ vertices)
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

```bash
# Local development (default)
export DATA_FOLDER=/Users/user/project/data/

# Jenkins production
export DATA_FOLDER=/IMAGE_WRITE/
```

## Technical Details

### Coordinate Spaces

- **Input**: BANC space (nanometers)
- **Intermediate**: JRC2018F space (micrometers)
- **Output**: JRC2018U (brain) or JRCVNC2018U (VNC) space (micrometers)

### Template Detection

Neurons are automatically classified as brain or VNC based on coordinate analysis and VFB database template mappings.

### Data Sources

- **BANC Skeletons**: `gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_skeletons/swcs-from-pcg-skel/`
- **BANC Meshes**: `gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes/meshes/`
- **VFB Database**: Neo4j database for neuron organization and template mapping

## Installation

### Prerequisites

```bash
# Python environment
pip install -r requirements.txt

# Google Cloud SDK (for data download)
brew install google-cloud-sdk  # macOS
# or apt-get install google-cloud-sdk  # Linux

# Optional: BANC transformation tools
git clone https://github.com/jasper-tms/the-BANC-fly-connectome.git
cd the-BANC-fly-connectome && pip install -e .
pip install git+https://github.com/jasper-tms/pytransformix.git
```

### Dependencies

Key Python packages:

- `navis`: Neuron analysis and visualization
- `vfb_connect`: VFB database connectivity
- `pynrrd`: NRRD file format support
- `flybrains`: Template brain registration
- `pandas`, `numpy`: Data processing

## Monitoring and Logging

The pipeline provides comprehensive logging:

```text
2025-08-17 16:07:52,466 - INFO - 🧠 Processing BANC neuron: 720575941559970319
2025-08-17 16:07:52,466 - INFO -   📁 VFB folder: VFB_00101567 → JRC2018U
2025-08-17 16:07:54,377 - INFO -     ✅ SWC: volume.swc
2025-08-17 16:07:58,471 - INFO -     ✅ OBJ (BANC mesh): volume.obj
2025-08-17 16:08:03,910 - INFO -     ✅ NRRD (from mesh): volume.nrrd
```

## Production Deployment

### Jenkins Integration

The pipeline is designed for Jenkins production deployment:

1. Set `DATA_FOLDER=/IMAGE_WRITE/`
2. Run with appropriate limits and format selection
3. Monitor logs for processing status
4. Output files are organized for VFB integration

### Error Handling

- Automatic fallback for missing mesh data (uses skeleton-based mesh)
- Resume capability from partial runs
- Comprehensive error logging and recovery
- Skip existing files to avoid reprocessing

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
