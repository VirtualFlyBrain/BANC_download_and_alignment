# Environment Configuration

Configuration for BANC → VFB production pipeline deployment across different environments.

## Environment Variables

### DATA_FOLDER

Controls the base path for output data organization:

- **Local Development**: Uses relative paths in current directory
- **Jenkins Production**: Set to `/IMAGE_WRITE/` for production data folder

```bash
# Local development (default)
python run_full_banc_production.py --limit 5

# Jenkins production
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --formats swc,obj,nrrd
```

## Pipeline Configuration

### Production Settings

```bash
# Jenkins production environment
export DATA_FOLDER=/IMAGE_WRITE/
export BANC_MAX_WORKERS=4
export BANC_LOG_LEVEL=INFO

# Full production run
python run_full_banc_production.py \
  --formats swc,obj,nrrd \
  --max-workers 4 \
  --output-dir vfb_banc_data
```

### Development Settings

```bash
# Local development environment
# (no environment variables needed)

# Test run
python run_full_banc_production.py \
  --limit 10 \
  --formats swc \
  --dry-run
```

## Data Sources Configuration

### VFB Database

- **Host**: kbw.virtualflybrain.org (production)
- **Database**: VFB kbw database
- **Authentication**: Standard VFB credentials
- **Query Filtering**: Only neurons with `EXISTS(r.folder)` condition

### BANC Public Data

- **Skeletons**: `gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_skeletons/`
- **Meshes**: `gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes/`
- **Access**: Public read access via gsutil
- **Format**: Neuroglancer precomputed mesh format

## Output Configuration

### File Organization

```text
${DATA_FOLDER}/vfb_banc_data/
├── processing_state.json
└── VFB/
    └── i/
        └── 0010/
            └── 5bke/
                └── VFB_00101567/
                    ├── volume.swc    # Transformed skeleton
                    ├── volume.obj    # High-quality mesh
                    └── volume.nrrd   # Volumetric data
```

### File Formats

- **SWC**: Standard skeleton format in template space
- **OBJ**: High-quality mesh from BANC precomputed data
- **NRRD**: Volumetric representation with template metadata

## Coordinate Transformation

### Template Spaces

- **Brain Neurons**: JRC2018U template space
- **VNC Neurons**: JRCVNC2018U template space
- **Detection**: Automatic based on coordinate analysis

### Transform Pipeline

```text
BANC Space (nm) → JRC2018F Space (µm) → Template Space (µm)
```

## Dependencies and Installation

### Required Python Packages

```bash
pip install -r requirements.txt
```

Key dependencies:

- `navis[all]`: Neuron analysis and visualization
- `vfb_connect`: VFB database connectivity
- `pynrrd`: NRRD file format support
- `flybrains`: Template brain registration

### Optional Tools

```bash
# BANC coordinate transformation (optional)
git clone https://github.com/jasper-tms/the-BANC-fly-connectome.git
pip install -e the-BANC-fly-connectome
pip install git+https://github.com/jasper-tms/pytransformix.git

# Google Cloud SDK (required for data access)
brew install google-cloud-sdk  # macOS
# or apt-get install google-cloud-sdk  # Linux
```

## Monitoring Configuration

### Logging

```bash
# Log file location
banc_production.log

# Log level configuration
export BANC_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Processing State

```bash
# State file location
${DATA_FOLDER}/vfb_banc_data/processing_state.json

# Contains:
# - Processed neurons list
# - Failed processing attempts
# - Performance statistics
# - Last run timestamp
```

## Environment-Specific Settings

### Local Development

```bash
# Default configuration
python run_full_banc_production.py --limit 5 --formats swc

# Working directory: ./vfb_banc_data/
# Log level: INFO
# Workers: 1
# Skip existing: true
```

### Jenkins Production

```bash
# Production configuration
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --formats swc,obj,nrrd --max-workers 4

# Working directory: /IMAGE_WRITE/vfb_banc_data/
# Log level: INFO
# Workers: 4
# Resume: automatic
```

## Troubleshooting

### Environment Issues

1. **DATA_FOLDER not set**: Uses current directory for local development
2. **Permission errors**: Check write access to DATA_FOLDER
3. **Network connectivity**: Verify VFB database and Google Cloud access
4. **Memory constraints**: Reduce max-workers for limited environments

### Performance Tuning

```bash
# High-performance environment
export BANC_MAX_WORKERS=8
python run_full_banc_production.py --max-workers 8

# Memory-constrained environment
export BANC_MAX_WORKERS=1
python run_full_banc_production.py --max-workers 1 --formats swc
```
