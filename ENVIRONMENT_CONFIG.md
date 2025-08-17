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

## Path Resolution

The pipeline resolves output paths based on the DATA_FOLDER environment:

### Local Development

```bash
# No DATA_FOLDER set
Output: ./vfb_banc_data/VFB/i/0010/5bke/VFB_00101567/BANC_ID/
```

### Jenkins Production

```bash
# DATA_FOLDER=/IMAGE_WRITE/
Output: /IMAGE_WRITE/vfb_banc_data/VFB/i/0010/5bke/VFB_00101567/BANC_ID/
```

## VFB Database Configuration

### Connection Parameters

- **Server**: kbw.virtualflybrain.org
- **Port**: 7474
- **Authentication**: Neo4j credentials
- **Database**: VFB knowledge base

### Production Constraints

The pipeline uses `EXISTS(r.folder)` condition to only process neurons with allocated folder information, which is critical during ongoing data loading where folder information is added once per day.

## Usage Examples

### Local Testing

```bash
# Test pipeline with small dataset
python run_full_banc_production.py --limit 3 --dry-run

# Process test neurons locally
python run_full_banc_production.py --limit 3 --formats swc
```

### Production Deployment

```bash
# Set production environment
export DATA_FOLDER=/IMAGE_WRITE/

# Full production run
python run_full_banc_production.py \
  --formats swc,obj,nrrd \
  --max-workers 4
```
