# BANC Connectome Download Setup

## Python Dependencies

```bash
pip install navis
pip install flybrains
pip install fafbseg  # Now supports BANC through dataset='banc'
pip install pandas
pip install vfb-connect
pip install rpy2  # Optional but recommended for better R integration
```

## R Dependencies

You need R installed with the following packages:

```r
# Install pak for easy package management
install.packages("pak")

# Install bancr package from GitHub
pak::pkg_install("flyconnectome/bancr")

# Install nat (should be installed as dependency)
install.packages("nat")
```

## Environment Variables

Set these before running the script:

```bash
export password="your_neo4j_password"
export max_chunk_size=10  # Optional, default is 10
export max_workers=5      # Optional, default is 5
export redo=false         # Set to 'true' to reprocess existing files
```

## Important Notes

### 1. BANC Data Access
The BANC dataset is available through the flywire package using `dataset='banc'`. The script uses:
- `flywire.get_skeletons(body_id, dataset='banc')` for skeleton data
- `flywire.get_mesh_neuron(body_id, dataset='banc', lod=2)` for mesh data

You may need to set up authentication tokens if required for BANC access.

### 2. Neo4j Query
The script uses the dataset identifier **'Bates2025'** for BANC data in the VFB database. The query structure matches the pattern used for other connectome datasets.

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
