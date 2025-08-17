# BANC Production Pipeline Usage Guide

This guide shows how to run the complete BANC→VFB production pipeline that processes all BANC neurons from the VFB database.

## Environment Configuration

### DATA_FOLDER Environment Variable

The pipeline uses the `DATA_FOLDER` environment variable to handle different deployment environments:

**Local Development:**
```bash
export DATA_FOLDER=/Users/username/project/data/    # Custom local path
# OR use default /data/ (creates subfolder in repo)
```

**Jenkins Production:**
```bash
export DATA_FOLDER=/IMAGE_WRITE/    # Jenkins server path mapping
```

**Path Resolution:**
- `--output-dir /data/vfb` + `DATA_FOLDER=/IMAGE_WRITE/` → `/IMAGE_WRITE/vfb/`
- `--output-dir vfb_banc_data` + `DATA_FOLDER=/custom/path/` → `/custom/path/vfb_banc_data/`

## Quick Start

### 1. Test Run (Recommended First)

```bash
# Test with 2 neurons in dry-run mode
python run_full_banc_production.py --limit 2 --dry-run

# Test actual processing with 1 neuron
python run_full_banc_production.py --limit 1
```

### 2. Production Run

```bash
# Process all BANC neurons from VFB database
python run_full_banc_production.py

# Jenkins production with environment mapping
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --output-dir /data/vfb --formats swc,obj,nrrd

# Resume from previous run (automatically skips existing files)
python run_full_banc_production.py --resume --skip-existing
```

## Pipeline Features

### ✅ **Complete Automation**
- Queries VFB database for all BANC neurons
- Downloads real data from public BANC Google Cloud bucket
- Transforms coordinates to proper template spaces
- Creates all required output formats

### ✅ **Smart Processing**
- **Automatic template detection**: Brain neurons → JRC2018U, VNC neurons → JRCVNC2018U
- **Resume capability**: Picks up where it left off after interruption
- **Skip existing**: Automatically skips already processed neurons
- **Error handling**: Continues processing other neurons if one fails

### ✅ **Proper Output Structure**

```
vfb_banc_data/
├── JRC2018U/                    # Brain neurons
│   ├── BANC_720575941350274352/
│   │   ├── BANC_720575941350274352.swc    # Skeleton (micrometers)
│   │   ├── BANC_720575941350274352.obj    # 3D mesh
│   │   ├── BANC_720575941350274352.nrrd   # Volume (with voxel metadata)
│   │   └── BANC_720575941350274352.json   # Metadata
│   └── BANC_[NEURON_ID]/
└── JRCVNC2018U/                 # VNC neurons
    └── BANC_[NEURON_ID]/
```

### ✅ **Correct Metadata**
- **Units**: All coordinates in micrometers
- **Voxel sizes**: JRC2018U (0.622µm), JRCVNC2018U (0.4µm)
- **Space orientation**: Left-posterior-superior
- **Provenance**: Full processing metadata in JSON

## Command Line Options

```bash
python run_full_banc_production.py [options]

Options:
  --output-dir DIR        Output directory (default: vfb_banc_data)
  --formats LIST          Formats: swc,obj,nrrd (default: swc,obj,nrrd)
  --limit N               Process only N neurons (for testing)
  --max-workers N         Parallel workers (default: 1)
  --dry-run               Show what would be processed
  --no-skip-existing      Reprocess existing files
  --resume                Resume from previous run (default behavior)
```

## Examples

### Development/Testing

```bash
# See what neurons would be processed
python run_full_banc_production.py --limit 10 --dry-run

# Process 5 neurons for testing
python run_full_banc_production.py --limit 5

# Only create SWC files for quick testing
python run_full_banc_production.py --limit 3 --formats swc
```

### Production Deployment

```bash
# Full production run
python run_full_banc_production.py --output-dir /vfb/data

# High-throughput with parallel processing
python run_full_banc_production.py --max-workers 4 --output-dir /vfb/data

# Resume interrupted production run
python run_full_banc_production.py --resume --output-dir /vfb/data
```

## Monitoring and Logging

### Log Files
- **Console output**: Real-time progress
- **banc_production.log**: Detailed processing log
- **processing_state.json**: Resume state and error tracking

### Progress Tracking

```
🧠 Processing BANC neuron: 720575941350274352
  📥 Downloading skeleton...
  ✅ Downloaded: 230 nodes
  🎯 Template space: JRC2018U
  🔄 Transforming coordinates...
  ✅ Coordinates transformed
  📁 Creating output files...
    ✅ SWC: BANC_720575941350274352.swc
    ✅ OBJ: BANC_720575941350274352.obj
    ✅ NRRD: BANC_720575941350274352.nrrd
  📋 Metadata: BANC_720575941350274352.json
  🎉 Successfully processed 720575941350274352
```

## Error Handling

### Automatic Recovery
- **Network failures**: Retries downloads
- **Processing errors**: Continues with next neuron
- **Interruption**: Resume from exact point with `--resume`

### Failed Neuron Tracking
Failed neurons are logged in `processing_state.json`:

```json
{
  "failed": [
    {
      "neuron_id": "720575941350273472",
      "error": "Skeleton not found in public bucket",
      "timestamp": "2025-08-17T08:30:15"
    }
  ]
}
```

## Prerequisites

### Required Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install Google Cloud SDK
brew install google-cloud-sdk  # macOS
# apt-get install google-cloud-sdk  # Linux

# Install BANC transforms (for proper coordinate alignment)
./install_banc_transforms.sh
```

### Optional but Recommended

```bash
# Install ElastiX for advanced transforms
brew install elastix  # macOS
apt-get install elastix  # Linux
```

## Jenkins Integration

### Production Command

```bash
cd /path/to/BANC_download_and_alignment
python run_full_banc_production.py --output-dir /vfb/data --formats swc,obj,nrrd
```

### Scheduled Processing

```bash
# Daily incremental processing (new/updated neurons only)
0 2 * * * cd /path/to/BANC_download_and_alignment && python run_full_banc_production.py --output-dir /vfb/data --resume
```

## Output Validation

### Check Results

```bash
# Count processed neurons
find vfb_banc_data -name "*.swc" | wc -l

# Check for complete triplets (SWC+OBJ+NRRD)
find vfb_banc_data -name "BANC_*.swc" -exec dirname {} \; | \
  xargs -I {} sh -c 'echo -n "{}: "; ls {}/*.{swc,obj,nrrd} 2>/dev/null | wc -l'

# View processing log
tail -f banc_production.log
```

### Quality Checks
Each processed neuron includes:
- ✅ Valid SWC with proper coordinates (micrometers)
- ✅ 3D mesh OBJ file
- ✅ NRRD volume with correct voxel metadata
- ✅ JSON metadata with provenance information

## Troubleshooting

### Common Issues

**"No neurons found in VFB"**
- Check VFB database connection
- Verify password in environment: `export password=your_vfb_password`

**"BANC transforms not available"**
- Run: `./install_banc_transforms.sh`
- Pipeline will use identity transform as fallback

**"NRRD creation failed"**
- Install: `pip install pynrrd`

**"Google Cloud SDK not available"**
- Install: `brew install google-cloud-sdk`
- Ensure `gsutil` is in PATH

### Performance Tuning

**Memory usage**: Use `--max-workers 1` for large neurons
**Network issues**: Pipeline automatically retries failed downloads
**Disk space**: ~10MB per neuron for all formats

---

## Summary

This pipeline provides **complete automation** for processing all BANC neurons:

1. **Input**: VFB database query → List of BANC neurons
2. **Processing**: Download → Transform → Convert → Save
3. **Output**: Template-organized files with proper metadata
4. **Reliability**: Resume capability, error handling, progress tracking

**Ready for production deployment with Jenkins scheduling.**
