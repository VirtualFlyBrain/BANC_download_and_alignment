# BANC Alignment Pipeline Documentation

## Overview
This document describes how the BANC alignment pipeline correctly handles both brain and VNC regions from the BANC connectome data and aligns them to their respective template spaces.

## Template Mapping

### VFB Template IDs to Coordinate Spaces
- **VFB_00101567** → **JRC2018U** (Brain template)
- **VFB_00200000** → **JRCVNC2018U** (VNC template)

### Template Characteristics
| Template | VFB ID | Coordinate Space | Typical Dimensions | Voxel Size |
|----------|--------|------------------|-------------------|------------|
| Brain | VFB_00101567 | JRC2018U | 1211×567×175 (W>H) | 0.622 µm |
| VNC | VFB_00200000 | JRCVNC2018U | 660×1290×382 (H>W) | 0.4 µm |

## Transformation Pipeline

### Two-Step Transformation Process

#### Step 1: BANC → Intermediate Template (BANC-specific transforms)
Uses official BANC transformation functions from `fanc.transforms.template_alignment`:

**Brain Neurons:**
```
BANC (nm) → [warp_points_BANC_to_brain_template] → JRC2018F (µm)
```

**VNC Neurons:**
```
BANC (nm) → [warp_points_BANC_to_vnc_template] → JRCVNC2018F (µm)
```

#### Step 2: Intermediate → Final Template (navis-flybrains)
Uses standard navis flybrains transformations:

**Brain Neurons:**
```
JRC2018F → [navis.xform_brain] → JRC2018U
```

**VNC Neurons:**
```
JRCVNC2018F → [navis.xform_brain] → JRCVNC2018U
```

## Implementation Details

### Database Query and Template Detection
1. VFB Neo4j database provides `template_id` for each neuron
2. `get_template_space_from_folder()` maps VFB template IDs to coordinate spaces
3. Pipeline routes neurons to appropriate transformation chain

### Coordinate Transformation Logic
```python
# Main processing determines target based on VFB template assignment
if 'VNC' in template_space:
    transformed = transform_skeleton_coordinates(skeleton, 'BANC', 'JRCVNC2018U')
else:
    transformed = transform_skeleton_coordinates(skeleton, 'BANC', 'JRC2018U')
```

### File Organization
Neurons are saved in VFB-compatible folder structure:
```
vfb_banc_data/
├── VFB/i/0010/5bke/VFB_00101567/  # Brain neuron
│   ├── volume.swc
│   ├── volume.obj
│   └── volume.nrrd
└── VFB/i/0020/0000/VFB_00200000/  # VNC neuron (future)
    ├── volume.swc
    ├── volume.obj
    └── volume.nrrd
```

## Dependencies

### Required for BANC Transformations
1. **BANC Repository**: `git clone https://github.com/jasper-tms/the-BANC-fly-connectome.git`
2. **pytransformix**: `pip install git+https://github.com/jasper-tms/pytransformix.git`
3. **Elastix binary**: `brew install elastix` (macOS) or equivalent

### Installation
Run the installation script:
```bash
bash install_banc_transforms.sh
```

## Quality Validation

### Template Assignment Verification
Check neuron dimensions against expected template characteristics:
- **Brain neurons**: Typically have coordinates fitting within JRC2018U bounds
- **VNC neurons**: Should have elongated anterior-posterior geometry (height > width)

### Current Issue Resolution
The neuron `720575941559970319` was previously:
- ❌ Assigned to `VFB_00101567` (brain template)
- ❌ Generated height > width geometry (500 × 271 µm)
- ✅ Should be reassigned to `VFB_00200000` (VNC template)

With the updated VNC `in_register_with` edges in the database, this neuron should now be correctly processed through the VNC transformation pipeline.

## Testing
To verify correct template assignment:
1. Check VFB database `template_id` assignment
2. Verify transformation chain selection in logs
3. Validate output file dimensions match expected template geometry
