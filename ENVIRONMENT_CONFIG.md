# Environment Configuration

Configuration guide for deploying the BANC → VFB production pipeline across different environments.

## Environment Variables

### DATA_FOLDER

Controls the base path for output data organization:

```bash
# Local development (default - uses current directory)
python run_full_banc_production.py --limit 5

# Jenkins production (set to production data folder)
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --formats swc,obj,nrrd
```

### Optional Environment Variables

```bash
# Maximum number of parallel workers
export BANC_MAX_WORKERS=4

# Logging level
export BANC_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## Environment-Specific Configurations

### Local Development

```bash
# Default configuration (no environment variables needed)
python run_full_banc_production.py \
  --limit 10 \
  --formats swc \
  --dry-run

# Working directory: ./vfb_banc_data/
# Log level: INFO
# Workers: 1
# Skip existing: true
```

### Jenkins Production

```bash
# Production configuration
export DATA_FOLDER=/IMAGE_WRITE/
export BANC_MAX_WORKERS=4
export BANC_LOG_LEVEL=INFO

python run_full_banc_production.py \
  --formats swc,obj,nrrd \
  --max-workers 4 \
  --output-dir vfb_banc_data

# Working directory: /IMAGE_WRITE/vfb_banc_data/
# Resume: automatic from previous runs
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

### Template Spaces and Coordinate Transformation

- **Brain Neurons**: JRC2018U template space
- **VNC Neurons**: JRCVNC2018U template space  
- **Detection**: Automatic based on coordinate analysis
- **Pipeline**: BANC Space (nm) → JRC2018F Space (µm) → Template Space (µm)

## Monitoring Configuration

### Logging
- **Log file**: `banc_production.log` in working directory
- **Format**: Timestamped with progress indicators and emojis
- **Levels**: DEBUG, INFO, WARNING, ERROR

### Processing State
- **State file**: `${DATA_FOLDER}/vfb_banc_data/processing_state.json`
- **Contains**: Processed neurons, failed attempts, performance stats, timestamps

## Performance Tuning

### High-Performance Environment
```bash
export BANC_MAX_WORKERS=8
python run_full_banc_production.py --max-workers 8
```

### Memory-Constrained Environment  
```bash
export BANC_MAX_WORKERS=1
python run_full_banc_production.py --max-workers 1 --formats swc
```

## Troubleshooting

### Common Issues

1. **DATA_FOLDER not set**: Uses current directory for local development
2. **Permission errors**: Check write access to DATA_FOLDER
3. **Network connectivity**: Verify VFB database and Google Cloud access
4. **Memory constraints**: Reduce max-workers for limited environments

### Error Recovery
- **Resume capability**: Automatic resume from `processing_state.json`
- **Fallback mechanisms**: Skeleton-based mesh if BANC mesh unavailable
- **Skip existing**: Avoid reprocessing unless `--no-skip-existing` used

