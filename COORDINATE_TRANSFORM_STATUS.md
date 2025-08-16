## BANC Coordinate Transformation Status

### Current Situation (August 2025)

#### What We Found:
1. **BANC Public Data Available**: The BANC team has released comprehensive public data at `gs://lee-lab_brain-and-nerve-cord-fly-connectome/`
   - Neuron skeletons (SWC format) 
   - Neuron meshes
   - Annotations and metadata
   - Template alignment data

2. **Template Alignment Evidence**: In the templates directory, we found:
   - `JRC2018F_aligned240721_to_BANC.ng` - JRC2018F template aligned to BANC space
   - `banc-synapses-v1.1-brain_aligned240720_to_JRC2018F_brain.ng` - BANC brain aligned to JRC2018F
   - `banc-synapses-v1.1-VNC_aligned240721_to_JRC2018F_VNC.ng` - BANC VNC aligned to JRC2018F VNC

3. **navis-flybrains Support**: 
   - FANC (VNC) ↔ JRCVNC2018F transforms available (requires Elastix)
   - JRC2018F/M/U brain template transforms available
   - **BANC not yet registered as a template space**

#### What's Missing:
- **Transformation matrices/functions** to convert BANC neuron coordinates to JRC2018 spaces
- **BANC template registration** in navis-flybrains package
- **Programmatic access** to the alignment transformations

### Coordinate Spaces Overview:

```
BANC (Brain And Nerve Cord)
├── Brain region (z: 0-6206)
│   └── Should align to JRC2018F brain templates
└── VNC region (z: 1438-7009) 
    └── May align to FANC or JRCVNC2018F

Standard Templates (via navis-flybrains):
├── Brain: JRC2018F, JRC2018M, JRC2018U
├── VNC: JRCVNC2018F, JRCVNC2018M, JRCVNC2018U  
└── Combined: FANC (VNC portion only)
```

### Current Pipeline Status:

✅ **Working**: Download real BANC neurons from public bucket
✅ **Working**: Multi-format output (SWC, JSON, OBJ, NRRD)
✅ **Working**: VFB metadata integration
⚠️ **Limited**: Coordinate transformation (identity transform only)
⚠️ **Needed**: Proper BANC → JRC2018 alignment

### Next Steps:

#### Option 1: Wait for Official Integration
- Wait for BANC to be added to navis-flybrains
- Monitor BANC GitHub repo for transformation releases

#### Option 2: Derive Transforms from Available Data
- Extract transformation matrices from aligned templates in bucket
- Create custom BANC → JRC2018 transformation functions
- Register with navis-flybrains locally

#### Option 3: Use Regional Approximations
- For VNC neurons: Use FANC space (if coordinates align)
- For brain neurons: Derive approximate transforms
- Validate using anatomical landmarks

### For Production Use:

Current MVP can provide:
1. **Real BANC neuron data** (not mock data)
2. **Multiple output formats** for VFB
3. **Proper metadata** integration
4. **Scalable pipeline** for bulk processing

**Limitation**: Neurons will be in BANC native coordinates until proper transforms are available.

### Resources for Further Development:

- BANC Wiki: https://github.com/jasper-tms/the-BANC-fly-connectome/wiki
- BANC Paper: https://www.biorxiv.org/content/10.1101/2025.07.31.667571
- navis-flybrains: https://github.com/navis-org/navis-flybrains
- Public Data: gs://lee-lab_brain-and-nerve-cord-fly-connectome/
