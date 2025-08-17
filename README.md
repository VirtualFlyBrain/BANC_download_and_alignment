# BANC → VFB Production Pipeline

Complete production-ready pipeline for processing BANC connectome neurons from VFB database integration with automated folder organization.

## Overview

This pipeline integrates with the Virtual Fly Brain (VFB) knowledge base to automatically process BANC neurons from their production database, organizing output according to VFB folder structure and coordinate templates.

## Production Method

The production pipeline uses:

- ✅ **VFB Database Integration**: Queries VFB kbw database for BANC neurons
- ✅ **VFB Folder Organization**: Automatic folder structure based on database URLs  
- ✅ **Production Data Filtering**: Only processes neurons with allocated folder information
- ✅ **Multi-format Output**: Generates SWC, OBJ, NRRD, and JSON files
- ✅ **Environment Configuration**: Local development + Jenkins production deployment

## Quick Start

### Production Commands

```bash
# Production pipeline - process all available BANC neurons
python run_full_banc_production.py --formats swc,obj,nrrd

# Limited run for testing
python run_full_banc_production.py --limit 10 --formats swc

# Dry run to see what would be processed
python run_full_banc_production.py --limit 5 --dry-run
```

### Installation

```bash
# 1. Clone repository
git clone <this-repository>
cd BANC_download_and_alignment

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install BANC transforms (optional, for coordinate alignment)
./install_banc_transforms.sh
```

## Environment Configuration

### Local Development

```bash
# Uses relative paths in current directory
python run_full_banc_production.py --limit 5 --formats swc
```

### Jenkins Production

```bash
# Set production data folder
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --formats swc,obj,nrrd --max-workers 4
```

## Data Processing

### VFB Database Integration

- **Source**: VFB kbw database (kbw.virtualflybrain.org)
- **Query**: BANC neurons with `EXISTS(r.folder)` condition for production readiness
- **Organization**: Automatic folder structure from VFB database URLs
- **Templates**: Automatic mapping to JRC2018U and JRCVNC2018U coordinate spaces

### Output Formats

- **SWC**: Skeleton format for neuroanatomy tools
- **OBJ**: 3D mesh for visualization  
- **NRRD**: Volume format for analysis
- **JSON**: VFB metadata with processing information

### Folder Organization

Files organized according to VFB database folder structure:

```
vfb_banc_data/
├── VFB/i/0010/5bke/VFB_00101567/
│   └── BANC_720575941559970319/
│       ├── BANC_720575941559970319.swc
│       ├── BANC_720575941559970319.obj
│       ├── BANC_720575941559970319.nrrd
│       └── BANC_720575941559970319.json
└── processing_state.json
```

## Coordinate Transformation

- **Brain neurons**: BANC → JRC2018U template
- **VNC neurons**: BANC → JRCVNC2018U template
- **Detection**: Automatic based on y-coordinate threshold
- **Fallback**: Identity transform if BANC package not installed

## Dependencies

### Required

- Python 3.8+
- navis[all] >= 1.6.0
- pandas >= 2.0.0
- vfb-connect
- Google Cloud SDK (gsutil)

### Optional (for coordinate transforms)

- BANC package (from GitHub)
- pytransformix
- ElastiX binary

## Project Structure

```
├── run_full_banc_production.py  # Main production pipeline
├── process.py                   # Core processing functions
├── requirements.txt             # Python dependencies
├── install_banc_transforms.sh   # Coordinate transform setup
├── vfb_banc_data/              # Production output directory
├── README_PRODUCTION.md         # Production deployment guide
├── ENVIRONMENT_CONFIG.md        # Environment configuration
├── VFB_FOLDER_MAPPING.md        # VFB folder organization details
└── FOLDER_ORGANIZATION_UPDATE.md # Current pipeline status
```

## Command Line Options

```bash
python run_full_banc_production.py [OPTIONS]

Options:
  --output-dir DIR          Output directory (default: vfb_banc_data)
  --formats LIST            Output formats: swc,obj,nrrd,json (default: swc,obj,nrrd)
  --limit N                 Maximum neurons to process
  --max-workers N           Parallel processing workers (default: 2)
  --dry-run                 Show what would be processed without processing
  --no-skip-existing        Reprocess existing neurons
  --resume                  Resume from last processing state
```

## Production Deployment

### Local Testing

```bash
# Test with small dataset
python run_full_banc_production.py --limit 3 --dry-run

# Process test neurons
python run_full_banc_production.py --limit 3 --formats swc
```

### Jenkins Production

```bash
# Set environment for production paths
export DATA_FOLDER=/IMAGE_WRITE/

# Full production run
python run_full_banc_production.py 
  --formats swc,obj,nrrd 
  --max-workers 4 
  --output-dir vfb_banc_data
```

## Monitoring

The pipeline creates a `processing_state.json` file that tracks:

- Processed neurons
- Failed processing attempts  
- Last run timestamp
- Processing statistics

## VFB Database Integration

The pipeline queries the VFB database for BANC neurons using:

```cypher
MATCH (s:Site {short_form:'BANC626'})<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
WHERE exists(r.folder)
RETURN c.accession[0] as banc_id,
       i.short_form as vfb_id,
       t.short_form as template_id,
       r.folder[0] as folder_path
```

The `EXISTS(r.folder)` condition ensures only neurons with allocated folder information are processed, which is critical during ongoing data loading where folder information is added once per day.

## License

This project follows the same license as the BANC connectome data.
