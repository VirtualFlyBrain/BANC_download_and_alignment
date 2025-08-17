# VFB Folder URL to Local Path Mapping

## Overview
The BANC production pipeline now correctly maps VFB folder URLs to local filesystem paths using the `$DATA_FOLDER` environment variable, enabling proper organization based on VFB database structure.

## URL to Path Mapping

### VFB Folder URL Structure
VFB provides folder URLs in the format:
```
http://www.virtualflybrain.org/data/VFB/i/0010/5fa2/VFB_00101567/
```

### Local Path Resolution
The system extracts the path after `/data/` and combines it with `$DATA_FOLDER`:

**Development (local)**:
```bash
export DATA_FOLDER=/Users/username/project/test_output/
# Results in: /Users/username/project/test_output/VFB/i/0010/5fa2/VFB_00101567/
```

**Production (Jenkins)**:
```bash
export DATA_FOLDER=/IMAGE_WRITE/
# Results in: /IMAGE_WRITE/VFB/i/0010/5fa2/VFB_00101567/
```

## Examples

### JRC2018U Brain Template
- **VFB URL**: `http://www.virtualflybrain.org/data/VFB/i/0010/5fa2/VFB_00101567/`
- **Template ID**: `VFB_00101567` (JRC2018U)
- **Local Path**: `VFB/i/0010/5fa2/VFB_00101567`
- **Full Output**: `$DATA_FOLDER/VFB/i/0010/5fa2/VFB_00101567/BANC_720575941350274352/`

### JRCVNC2018U VNC Template  
- **VFB URL**: `http://www.virtualflybrain.org/data/VFB/i/0010/6000/VFB_00200000/`
- **Template ID**: `VFB_00200000` (JRCVNC2018U)
- **Local Path**: `VFB/i/0010/6000/VFB_00200000`
- **Full Output**: `$DATA_FOLDER/VFB/i/0010/6000/VFB_00200000/BANC_720575941350274112/`

## Implementation Details

### Database Query Enhancement
The Neo4j query now extracts the folder URL from `in_register_with` relationships:
```cypher
MATCH (s:Site {short_form:'BANC626'})<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
RETURN c.accession[0] as banc_id,
       i.short_form as vfb_id,
       t.short_form as template_id,
       r.folder[0] as folder_path,
       r.filename as filename,
       i.label as name
```

### URL Parsing Function
```python
def parse_vfb_folder_url(folder_path):
    """Extract local path from VFB folder URL."""
    if folder_path and 'virtualflybrain.org/data/' in folder_path:
        url_parts = folder_path.split('/data/')
        if len(url_parts) > 1:
            return url_parts[1].rstrip('/')  # Remove trailing slash
    return None
```

### Enhanced Neuron Data Structure
```python
{
    'id': '720575941350274352',
    'vfb_id': 'VFB_00105fa2',
    'name': 'BANC Neuron 720575941350274352',
    'template_id': 'VFB_00101567',
    'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/5fa2/VFB_00101567/',
    'local_folder_path': 'VFB/i/0010/5fa2/VFB_00101567',  # KEY: Local filesystem path
    'template_folder': 'VFB_00101567',  # For template mapping
    'status': 'ready'
}
```

## Final Output Structure

### Local Development
```
vfb_banc_data/
└── VFB/
    └── i/
        ├── 0010/
        │   ├── 5fa2/
        │   │   └── VFB_00101567/      # JRC2018U template
        │   │       └── BANC_720575941350274352/
        │   │           ├── BANC_720575941350274352.swc
        │   │           ├── BANC_720575941350274352.obj
        │   │           ├── BANC_720575941350274352.nrrd
        │   │           └── BANC_720575941350274352.json
        │   ├── 5fb1/
        │   │   └── VFB_00101567/      # JRC2018U template
        │   │       └── BANC_720575941350334256/
        │   └── 6000/
        │       └── VFB_00200000/      # JRCVNC2018U template
        │           └── BANC_720575941350274112/
```

### Production (Jenkins)
```
/IMAGE_WRITE/
└── VFB/
    └── i/
        ├── 0010/
        │   ├── 5fa2/
        │   │   └── VFB_00101567/      # JRC2018U template
        │   │       └── BANC_720575941350274352/
        │   │           ├── BANC_720575941350274352.swc
        │   │           ├── BANC_720575941350274352.obj
        │   │           ├── BANC_720575941350274352.nrrd
        │   │           └── BANC_720575941350274352.json
        │   └── [...]
```

## Benefits

1. **Database-Driven Organization**: Structure reflects VFB database folder organization
2. **Template Flexibility**: Supports multiple template spaces (JRC2018U, JRCVNC2018U, etc.)
3. **Environment Agnostic**: Works in both development and production with `$DATA_FOLDER`
4. **URL Preservation**: Maintains link between VFB URLs and local filesystem
5. **Scalable**: No hardcoded paths, fully dynamic based on database content

## Environment Configuration

### Development
```bash
export DATA_FOLDER=/Users/username/project/test_output/
python run_full_banc_production.py --limit 10
```

### Production (Jenkins)
```bash
export DATA_FOLDER=/IMAGE_WRITE/
python run_full_banc_production.py
```

The system automatically resolves paths based on the environment, ensuring consistent behavior across development and production deployments.
