# Production Pipeline Status

## Current Implementation

The BANC → VFB production pipeline is now fully operational with VFB database integration and proper folder organization.

## Key Features

### VFB Database Integration
- Direct queries to VFB kbw database for BANC neurons
- Production filtering using `EXISTS(r.folder)` condition
- Automatic folder URL parsing to filesystem paths

### Folder Organization
- VFB database folder URLs mapped to local filesystem structure
- Example: `http://www.virtualflybrain.org/data/VFB/i/0010/5bke/VFB_00101567/` → `VFB/i/0010/5bke/VFB_00101567`
- Individual BANC neuron subdirectories within VFB folder structure

### Multi-format Output
- **SWC**: Skeleton format for neuroanatomy
- **OBJ**: 3D mesh for visualization  
- **NRRD**: Volume format for analysis
- **JSON**: VFB metadata with processing information

### Environment Configuration
- Local development: Uses relative paths in current directory
- Jenkins production: `DATA_FOLDER=/IMAGE_WRITE/` for production deployment

## Production Query

Current Cypher query for VFB database:

```cypher
MATCH (s:Site {short_form:'BANC626'})<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
WHERE exists(r.folder)
RETURN c.accession[0] as banc_id,
       i.short_form as vfb_id,
       t.short_form as template_id,
       r.folder[0] as folder_path
```

## Current Status

### Processing State
- ✅ VFB database connection operational
- ✅ Production data filtering active (`EXISTS(r.folder)`)
- ✅ VFB folder organization implemented
- ✅ Multi-format export functional
- ✅ Environment configuration working

### Processed Neurons
- 3 neurons successfully processed with VFB folder organization
- Processing state maintained in `processing_state.json`
- Resume capability for production runs

## Usage

### Production Command
```bash
# Set production environment
export DATA_FOLDER=/IMAGE_WRITE/

# Run production pipeline
python run_full_banc_production.py --formats swc,obj,nrrd --max-workers 4
```

### Local Testing
```bash
# Test with small dataset
python run_full_banc_production.py --limit 3 --dry-run

# Process test neurons
python run_full_banc_production.py --limit 3 --formats swc
```
