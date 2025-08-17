# Technical Details

Detailed technical information for the BANC data processing pipeline.

## Architecture Overview

### Data Flow

```text
VFB Database → BANC Public Data → Coordinate Transform → VFB File Structure
     ↓              ↓                    ↓                    ↓
  Neuron IDs    Skeleton/Mesh     JRC2018U/VNC Space    volume.[swc|obj|nrrd]
```

### Coordinate Spaces and Transformations

- **Input**: BANC space (nanometers)
- **Intermediate**: JRC2018F space (micrometers)  
- **Output**: JRC2018U (brain) or JRCVNC2018U (VNC) space (micrometers)

### Template Detection

Neurons are automatically classified as brain or VNC based on:
- Coordinate analysis of neuron extent
- VFB database template mappings
- Automatic selection of appropriate template space

## Data Sources

### BANC Public Dataset

- **Base URL**: `gs://lee-lab_brain-and-nerve-cord-fly-connectome/`
- **Skeletons**: `neuron_skeletons/swcs-from-pcg-skel/`
- **Meshes**: `neuron_meshes/meshes/`
- **Format**: Neuroglancer precomputed mesh format (JSON + binary)

### VFB Database

- **Host**: kbw.virtualflybrain.org
- **Type**: Neo4j graph database
- **Query**: Neurons with `EXISTS(r.folder)` condition
- **Data**: Neuron organization, template mapping, VFB identifiers

## File Format Specifications

### SWC Files

- **Format**: Standard SWC (Space-separated values)
- **Units**: Micrometers
- **Coordinate System**: Template space (JRC2018U or JRCVNC2018U)
- **Processing**: Direct coordinate transformation from BANC skeleton data
- **Typical Size**: 4KB per neuron

### OBJ Files

- **Format**: Wavefront OBJ mesh format
- **Source**: BANC precomputed mesh fragments
- **Processing Steps**:
  1. Download JSON manifest and binary mesh data
  2. Parse binary mesh format (vertices + triangles)
  3. Apply coordinate transformation
  4. Generate OBJ with vertex normals
- **Quality**: High-detail meshes (70K+ vertices, 150K+ triangles)
- **Typical Size**: 5-10MB per neuron

### NRRD Files

- **Format**: Nearly Raw Raster Data
- **Source**: Generated from transformed OBJ meshes
- **Processing Steps**:
  1. Mesh voxelization using template-specific resolution
  2. Template metadata injection
  3. NRRD header generation with coordinate system info
- **Voxel Size**: 0.622µm (JRC2018U) or 0.4µm (JRCVNC2018U)
- **Typical Size**: 200-500KB per neuron

## Error Handling and Recovery

### Fallback Mechanisms

1. **Missing Mesh Data**: Falls back to skeleton-based mesh generation
2. **Network Failures**: Retry logic with exponential backoff
3. **Coordinate Transform Errors**: Skip neuron with detailed logging
4. **File Write Errors**: Cleanup partial files and retry

### Resume Capability

- **State File**: `processing_state.json` tracks completion status
- **Resume Logic**: Automatically skips completed neurons
- **Force Reprocess**: Use `--no-skip-existing` flag

### Logging and Monitoring

- **Log Format**: Timestamped with progress indicators
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Progress Tracking**: Emoji indicators for visual status
- **Error Context**: Full stack traces for debugging

## Performance Characteristics

### Processing Speed

- **Average**: ~15 seconds per neuron (including all formats)
- **Bottlenecks**: Mesh download and coordinate transformation
- **Parallelization**: Configurable worker processes

### Resource Usage

- **Memory**: ~500MB per worker process
- **Disk I/O**: Sequential write patterns
- **Network**: Burst downloads from Google Cloud Storage

### Scalability

- **Worker Processes**: Linear scaling up to I/O limits
- **Batch Processing**: Processes neurons in database query order
- **Memory Management**: Automatic cleanup between neurons

## Quality Assurance

### Validation Steps

1. **Coordinate Bounds**: Verify transforms produce reasonable coordinates
2. **File Integrity**: Check file sizes and format validity
3. **Template Alignment**: Validate against known anatomical landmarks
4. **Mesh Quality**: Verify vertex counts and triangle connectivity

### Known Limitations

1. **Coordinate Precision**: Limited by source data precision
2. **Template Coverage**: Some neurons may fall outside template bounds
3. **Mesh Artifacts**: Occasional gaps in BANC mesh data
4. **Processing Time**: Large meshes can take significant time

## Development and Testing

### Test Environment Setup

```bash
# Limited test run
python run_full_banc_production.py --limit 5 --dry-run

# Single format testing
python run_full_banc_production.py --limit 10 --formats swc

# Debug mode
python run_full_banc_production.py --limit 1 --verbose
```

### Code Organization

- `process.py`: Core processing logic and coordinate transformations
- `run_full_banc_production.py`: Main pipeline orchestration
- `requirements.txt`: Python dependencies
- `install_banc_transforms.sh`: Setup script for transformation tools

### Extension Points

1. **Custom Transforms**: Add new coordinate transformation methods
2. **Output Formats**: Implement additional file format generators
3. **Quality Filters**: Add neuron filtering based on quality metrics
4. **Batch Processing**: Modify for different batching strategies
