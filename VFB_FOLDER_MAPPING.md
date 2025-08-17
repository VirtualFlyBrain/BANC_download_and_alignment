# VFB Folder Organization

Documentation for VFB database folder URL parsing and local filesystem organization in the BANC production pipeline.

## VFB Database Folder Structure

The VFB database stores folder information as URLs that need to be parsed to local filesystem paths:

### Database URL Format

```
http://www.virtualflybrain.org/data/VFB/i/0010/5bke/VFB_00101567/
```

### Local Filesystem Path

```
VFB/i/0010/5bke/VFB_00101567
```

## URL to Path Mapping

The pipeline automatically converts VFB database folder URLs to local filesystem paths:

```python
# VFB Database URL
folder_url = "http://www.virtualflybrain.org/data/VFB/i/0010/5bke/VFB_00101567/"

# Extract path after /data/
url_parts = folder_url.split('/data/')
local_folder_path = url_parts[1].rstrip('/')  # Remove trailing slash

# Result: "VFB/i/0010/5bke/VFB_00101567"
```

## Complete Output Structure

Files are organized in the VFB folder structure with BANC neuron subdirectories:

```
vfb_banc_data/
├── VFB/i/0010/5bke/VFB_00101567/
│   └── BANC_720575941559970319/
│       ├── BANC_720575941559970319.swc
│       ├── BANC_720575941559970319.obj
│       ├── BANC_720575941559970319.nrrd
│       └── BANC_720575941559970319.json
├── VFB/i/0010/5bkf/VFB_00101567/
│   └── BANC_720575941559971087/
│       └── BANC_720575941559971087.swc
└── processing_state.json
```

## Template Mapping

VFB template IDs are mapped to coordinate spaces:

| Template ID | Coordinate Space | Description |
|-------------|------------------|-------------|
| VFB_00101567 | JRC2018U | Brain unisex template |
| VFB_00200000 | JRCVNC2018U | VNC unisex template |

## Production Query

The VFB database query retrieves folder information using the `folder_path` field:

```cypher
MATCH (s:Site {short_form:'BANC626'})<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
WHERE exists(r.folder)
RETURN c.accession[0] as banc_id,
       i.short_form as vfb_id,
       t.short_form as template_id,
       r.folder[0] as folder_path
```

The `EXISTS(r.folder)` condition ensures only neurons with allocated folder information are processed.
