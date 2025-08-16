# BANC → VFB Processing Pipeline

Complete pipeline for downloading BANC connectome neuron data and converting it to VFB-compatible formats.

## Overview

This pipeline processes neurons from the BANC (Brain and Nerve Cord) fly connectome dataset and prepares them for integration with the Virtual Fly Brain (VFB) knowledge base using **public BANC data** from Google Cloud Storage.

## Current Method

The pipeline uses:
- ✅ **Public BANC Data**: Downloads from `gs://lee-lab_brain-and-nerve-cord-fly-connectome/`
- ✅ **Official BANC Transforms**: Uses BANC team's coordinate transformation functions
- ✅ **Multi-format Output**: Generates SWC, OBJ, and NRRD files
- ✅ **No Authentication Required**: Public bucket access via gsutil

## Quick Start

### Production Command

```bash
# Process single neuron
python run_banc_pipeline.py 720575941350274352 --formats swc,obj,nrrd

# Process multiple neurons  
python run_banc_pipeline.py 720575941350274352 720575941350334256 --formats swc
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

## Dependencies

### Required
- Python 3.8+
- navis[all] >= 1.6.0
- pandas >= 2.0.0
- Google Cloud SDK (gsutil)

### Optional (for coordinate transforms)
- BANC package (from GitHub)
- pytransformix
- ElastiX binary

## Data Processing

### Input
- BANC neuron segment IDs (e.g., `720575941350274352`)
- Available neurons listed at: `gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_skeletons/swcs-from-pcg-skel/`

### Output
- **SWC**: Skeleton format for neuroanatomy tools
- **OBJ**: 3D mesh for visualization
- **NRRD**: Volume format for analysis
- **JSON**: VFB metadata

### Coordinate Transformation
- **BANC** → **JRC2018F** (brain neurons)
- **BANC** → **JRCVNC2018F** (VNC neurons)
- Automatic brain/VNC detection
- Fallback to identity transform if BANC transforms not installed

## Project Structure

```
├── process.py              # Core processing functions
├── run_banc_pipeline.py    # Command-line interface
├── test_pipeline_status.py # Pipeline validation
├── install_banc_transforms.sh # Coordinate transform setup
└── requirements.txt        # Python dependencies
```

## Testing

```bash
# Test pipeline functionality
python test_pipeline_status.py

# Quick validation
python quick_test.py
```

### 3. Transformation Strategy
The bancr R package's `banc_to_JRC2018F` function has a `region` parameter:
- `region="brain"` - Transforms to JRC2018F brain template
- `region="VNC"` - Transforms to JRC2018F VNC template

For neurons spanning both regions (DNs, ANs, SAs), the script:
- Transforms to **both** templates separately
- Saves multiple output files:
  - `volume.swc` - Primary region transformation
  - `volume_brain.swc` - Brain template transformation
  - `volume_vnc.swc` - VNC template transformation
- Auto-detects primary region based on spatial extent

This ensures proper alignment regardless of where the neuron extends in the CNS.

### 4. R Integration Options

The script provides two ways to use R:

**Option 1: Using rpy2 (Recommended)**
- Install rpy2: `pip install rpy2`
- More efficient, keeps R session active

**Option 2: Using subprocess**
- No additional Python packages needed
- R must be in your system PATH
- Slightly slower due to repeated R initialization

### 5. Mesh Transformation
Mesh transformation through R may require additional handling. The current implementation:
- Saves mesh as OBJ format
- Transforms vertices using bancr
- Reloads transformed mesh

This may need adjustment based on how bancr handles mesh data.

## Testing

### Test Neuron
Using verified BANC neuron: **720575941499161569**
- View online: https://codex.flywire.ai/app/cell_details?root_id=720575941499161569&dataset=banc
- This neuron can be used to verify the pipeline is working correctly

### Quick Access Test
First, verify BANC access works:
```bash
python test_banc_access.py [OPTIONAL_BODY_ID]
```

### Database Query Test
Start with a small subset by adding a LIMIT clause to your Neo4j query:

```cypher
MATCH (d:DataSet {short_form:'Bates2025'})<-[:has_source]-(i:Individual)<-[:depicts]-(ic:Individual)
-[r:in_register_with]->(tc:Template)
RETURN r.filename[0] as root_id, r.folder[0] as folder
LIMIT 5
```

### Python Console Test
Test the flywire BANC access directly:
```python
from fafbseg import flywire
# Using verified BANC neuron from codex.flywire.ai
test_id = 720575941499161569  
skeleton = flywire.get_skeletons(test_id, dataset='banc')
print(skeleton)
```

### Single Neuron Test
Test the full pipeline with one neuron:
```bash
# Process the test neuron (720575941499161569)
python test_single_neuron.py

# Or specify a different neuron
python test_single_neuron.py 720575941499161569 ./output_dir
```

## Output Organization

### VFB Folder Structure
Files follow the standard VFB hierarchy:
`/VFB/i/[first_4_digits]/[next_4_digits]/[template_short_form]/`

| Template | VFB Short Form | Description |
|----------|---------------|-------------|
| JRC2018U | VFB_00101567 | Brain unisex template |
| JRC2018VNCunisex | VFB_00200000 | VNC unisex template |

Example output paths:
```
# DN (descending neuron) - spans both regions
.../VFB/i/1234/5678/VFB_00101567/volume.swc  # Brain alignment
.../VFB/i/1234/5678/VFB_00200000/volume.swc  # VNC alignment

# Local brain neuron - single region
.../VFB/i/1234/5678/VFB_00101567/volume.swc

# Motor neuron - VNC only
.../VFB/i/1234/5678/VFB_00200000/volume.swc
```

The Neo4j query provides the base folder URL with the neuron path structure, and the script appends the appropriate template short_form based on successful transformations.
