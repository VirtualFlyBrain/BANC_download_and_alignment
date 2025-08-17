# Environment Configuration Examples

## Local Development

### Option 1: Use default /data/ (creates subfolder in repo)
```bash
# No DATA_FOLDER set - uses default /data/
python run_full_banc_production.py --output-dir vfb_banc_data --limit 5
# Creates: ./vfb_banc_data/JRC2018U/ and ./vfb_banc_data/JRCVNC2018U/
```

### Option 2: Custom local path
```bash
export DATA_FOLDER=/Users/username/myproject/data/
python run_full_banc_production.py --output-dir /data/vfb --limit 5
# Creates: /Users/username/myproject/data/vfb/JRC2018U/ and /Users/username/myproject/data/vfb/JRCVNC2018U/
```

### Option 3: Relative to repo
```bash
export DATA_FOLDER=/Users/rcourt/GIT/BANC_download_and_alignment/test_output/
python run_full_banc_production.py --output-dir /data/vfb --limit 5
# Creates: /Users/rcourt/GIT/BANC_download_and_alignment/test_output/vfb/JRC2018U/
```

## Jenkins Production

### Standard Jenkins deployment
```bash
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --output-dir /data/vfb --formats swc,obj,nrrd
# Creates: /IMAGE_WRITE/vfb/JRC2018U/ and /IMAGE_WRITE/vfb/JRCVNC2018U/
```

### Jenkins with custom template names
```bash
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py \
  --output-dir /data/banc_processed \
  --brain-template JRC2018U \
  --vnc-template JRCVNC2018U \
  --formats swc,obj,nrrd
# Creates: /IMAGE_WRITE/banc_processed/JRC2018U/ and /IMAGE_WRITE/banc_processed/JRCVNC2018U/
```

## Path Resolution Logic

The script resolves paths as follows:

1. **Check DATA_FOLDER environment variable**
   - Default: `/data/` if not set
   - Jenkins: `/IMAGE_WRITE/`
   - Custom: Any path you specify

2. **Apply path mapping**
   - `--output-dir /data/vfb` + `DATA_FOLDER=/IMAGE_WRITE/` → `/IMAGE_WRITE/vfb/`
   - `--output-dir vfb_banc_data` + `DATA_FOLDER=/custom/` → `/custom/vfb_banc_data/`

3. **Create template subdirectories**
   - Brain neurons: `{resolved_path}/{brain_template}/`
   - VNC neurons: `{resolved_path}/{vnc_template}/`

## Output Structure

```
{DATA_FOLDER}/{output-dir}/
├── {brain_template}/           # Default: JRC2018U
│   └── BANC_{neuron_id}/
│       ├── BANC_{neuron_id}.swc
│       ├── BANC_{neuron_id}.obj
│       ├── BANC_{neuron_id}.nrrd
│       └── BANC_{neuron_id}.json
└── {vnc_template}/             # Default: JRCVNC2018U
    └── BANC_{neuron_id}/
        └── ...
```

## Testing Commands

### Test path resolution without processing
```bash
# Test local custom path
export DATA_FOLDER=/tmp/test_banc/
python run_full_banc_production.py --limit 1 --dry-run --output-dir /data/vfb

# Test Jenkins-style path (will fail directory creation, but shows resolution)
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py --limit 1 --dry-run --output-dir /data/vfb
```

### Test actual processing locally
```bash
export DATA_FOLDER=/Users/rcourt/GIT/BANC_download_and_alignment/test_output/
python run_full_banc_production.py --limit 1 --output-dir /data/vfb --formats swc
```
