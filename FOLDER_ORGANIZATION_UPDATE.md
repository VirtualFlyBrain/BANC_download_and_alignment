# VFB Folder Organization Update

## Summary
Updated the BANC production pipeline to use VFB database folder information for proper template organization, replacing hardcoded template mapping with dynamic folder-based structure from Neo4j database.

## Key Changes

### 1. Neo4j Query Structure Update
**Fixed Cypher query** in `process.py` to correctly access folder information:
```cypher
MATCH (s:Site {short_form:'BANC626'})<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
RETURN c.accession[0] as banc_id,
       i.short_form as vfb_id,
       t.short_form as template_id,
       r.folder[0] as folder_path,
       r.filename as filename,
       i.label as name
```

### 2. Updated Data Structure
**Enhanced neuron data** to include VFB folder information:
```python
{
    'id': '720575941350274352',
    'vfb_id': 'VFB_00105fa2', 
    'name': 'BANC Neuron 720575941350274352',
    'template_id': 'VFB_00101567',
    'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/5fa2/VFB_00101567/',
    'template_folder': 'VFB_00101567',  # Key for organization
    'status': 'ready'
}
```

### 3. Folder-Based Template Mapping
**Automatic template space detection** from VFB folder short_form:
```python
template_mappings = {
    'VFB_00101567': 'JRC2018U',      # JRC2018U brain template
    'VFB_00200000': 'JRCVNC2018U',   # VNC template
}
```

### 4. Dynamic Output Organization
**Organized output structure** based on VFB folders:
```
vfb_banc_data/
├── VFB_00101567/           # JRC2018U brain template
│   ├── BANC_720575941350274352/
│   │   ├── BANC_720575941350274352.swc
│   │   ├── BANC_720575941350274352.obj
│   │   ├── BANC_720575941350274352.nrrd
│   │   └── BANC_720575941350274352.json
│   └── BANC_720575941350334256/
│       └── ...
└── VFB_00200000/           # JRCVNC2018U VNC template  
    └── BANC_720575941350274112/
        └── ...
```

## Benefits

1. **Database-Driven**: Organization reflects actual VFB database structure
2. **Template Flexibility**: Supports multiple template spaces automatically
3. **Scalable**: No hardcoded template assignments
4. **Maintainable**: Changes in VFB database automatically propagate
5. **Accurate**: Uses real folder paths from in_register_with relationships

## Production Ready
✅ Updated production pipeline (`run_full_banc_production.py`)
✅ Environment configuration support (DATA_FOLDER mapping)
✅ Resume functionality with folder organization
✅ Comprehensive error handling and logging
✅ Test data structure matches real database format

The system now correctly uses VFB database folder information to organize BANC neuron outputs by their appropriate template spaces, providing accurate and maintainable template mapping.
