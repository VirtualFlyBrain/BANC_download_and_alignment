# BANC → VFB Production Pipeline

Production-ready pipeline for processing BANC connectome neuron data from VFB database integration.

## Production Overview

This pipeline queries the VFB kbw database for BANC neurons and processes them according to VFB folder organization standards.

**Key Features:**

- ✅ **VFB Database Integration**: Direct queries to VFB kbw database
- ✅ **Production Data Filtering**: Only processes neurons with allocated folder information
- ✅ **VFB Folder Organization**: Automatic folder structure from database URLs
- ✅ **Environment Configuration**: Local development + Jenkins production deployment
- ✅ **Multi-format Output**: SWC, OBJ mesh, NRRD volume, JSON metadata

## Jenkins Deployment

### Production Commands

```bash
# Set production environment
export DATA_FOLDER=/IMAGE_WRITE/

# Full production pipeline
python run_full_banc_production.py --formats swc,obj,nrrd --max-workers 4

# Limited production run
python run_full_banc_production.py --limit 100 --formats swc,obj
```

### Installation

```bash
# Production installation
pip install -r requirements.txt

# Optional: Install BANC coordinate transforms
./install_banc_transforms.sh
```

## VFB Database Integration

### Data Source

- **Database**: VFB kbw database (kbw.virtualflybrain.org)
- **Query**: BANC neurons with `EXISTS(r.folder)` condition
- **Organization**: VFB folder URLs automatically parsed to filesystem paths
- **Templates**: JRC2018U (brain) and JRCVNC2018U (VNC) coordinate spaces

### Production Query

```cypher
MATCH (s:Site {short_form:'BANC626'})<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
WHERE exists(r.folder)
RETURN c.accession[0] as banc_id,
       i.short_form as vfb_id,
       t.short_form as template_id,
       r.folder[0] as folder_path
```

The `EXISTS(r.folder)` condition ensures only neurons with allocated folder information are processed, which is critical during ongoing data loading where folder information is added once per day.

## Processing Pipeline

### Step 1: VFB Database Query

- Query VFB database for BANC neurons with folder allocation
- Parse VFB folder URLs to local filesystem paths
- Map template IDs to coordinate spaces

### Step 2: Skeleton Download

- Download skeleton data from BANC public bucket
- Load with navis for processing
- Validate skeleton structure

### Step 3: Coordinate Transformation

- Transform BANC coordinates to VFB template spaces
- Brain neurons: BANC → JRC2018U
- VNC neurons: BANC → JRCVNC2018U  
- Automatic region detection based on coordinates

### Step 4: Multi-format Export

- **SWC**: Skeleton format for neuroanatomy
- **OBJ**: 3D mesh for visualization
- **NRRD**: Volume format for analysis
- **JSON**: VFB metadata with processing information

### Step 5: VFB Folder Organization

- Organize files according to VFB database folder structure
- Example: `VFB/i/0010/5bke/VFB_00101567/BANC_720575941559970319/`
- Maintain processing state for resume capability

## Environment Configuration

### Local Development

```bash
# Default - uses current directory
python run_full_banc_production.py --limit 5 --formats swc
```

### Jenkins Production

```bash
# Set production data folder
export DATA_FOLDER=/IMAGE_WRITE/

# Full production run
python run_full_banc_production.py --formats swc,obj,nrrd --max-workers 4
```

## Command Line Reference

```bash
python run_full_banc_production.py [OPTIONS]

Options:
  --output-dir DIR          Output directory (default: vfb_banc_data)
  --formats LIST            Formats: swc,obj,nrrd,json (default: swc,obj,nrrd)
  --limit N                 Maximum neurons to process
  --max-workers N           Parallel workers (default: 2)
  --dry-run                 Show what would be processed
  --no-skip-existing        Reprocess existing neurons
  --resume                  Resume from last state
```

## Output Structure

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

## Monitoring and Validation

The pipeline maintains a `processing_state.json` file with:

- Processed neuron IDs
- Failed processing attempts
- Last run timestamp
- Processing statistics

## Production Deployment Checklist

### Prerequisites

1. ✅ Python 3.8+ environment
2. ✅ Required packages: `pip install -r requirements.txt`
3. ✅ Google Cloud SDK: `gsutil` command available
4. ✅ VFB database access (kbw.virtualflybrain.org)

### Environment Setup

```bash
# Production environment variable
export DATA_FOLDER=/IMAGE_WRITE/

# Verify VFB database connectivity
python -c "from process import get_vfb_banc_neurons; print('VFB connection OK')"
```

### Production Run

```bash
# Start production processing
python run_full_banc_production.py \
  --formats swc,obj,nrrd \
  --max-workers 4 \
  --output-dir vfb_banc_data
```
