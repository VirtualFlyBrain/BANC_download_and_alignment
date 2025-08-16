#!/usr/bin/env python3

import os
import glob
import navis
import flybrains
import pandas as pd
import numpy as np
import subprocess
import tempfile
import requests
import json
from pathlib import Path
from datetime import datetime
from vfb_connect.cross_server_tools import VfbConnect
from concurrent.futures import ThreadPoolExecutor, as_completed
from fafbseg import flywire  # flywire package now supports BANC through dataset='banc' parameter

# Import CAVEclient and meshparty for direct BANC mesh and skeleton access
try:
    from caveclient import CAVEclient
    from meshparty import trimesh_io
    import trimesh
    BANC_AVAILABLE = True
except ImportError as e:
    BANC_AVAILABLE = False

# Try to import rpy2 for R integration
try:
    import rpy2.robjects as ro
    from rpy2.robjects import pandas2ri
    from rpy2.robjects.packages import importr
    pandas2ri.activate()
    R_AVAILABLE = True
except ImportError:
    R_AVAILABLE = False


def get_vfb_banc_neurons(limit=None):
    """
    Query VFB database for BANC neuron records that need processing.
    
    Args:
        limit (int, optional): Maximum number of neurons to return
        
    Returns:
        list: List of neuron dictionaries with id, name, status
    """
    try:
        # VFB database connection parameters
        server = 'kbw.virtualflybrain.org'
        password = os.getenv('password', 'banana2-funky-Earthy-Irvin-Tactful0-felice9')
        
        print(f"Querying VFB database for BANC neurons...")
        
        # Initialize VFB connection
        vfb = VfbConnect(
            neo_endpoint=f'http://{server}:7474',
            neo_credentials=('neo4j', password)
        )
        
        # Query for BANC neurons
        query = """
        MATCH (n:Individual)
        WHERE n.short_form CONTAINS 'BANC'
        RETURN n.short_form as id, n.label as name, 'ready' as status
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = vfb.neo_query_wrapper(query)
        
        if not results:
            # If no BANC-specific results, try a broader query for testing
            print("No BANC-specific neurons found, trying broader query...")
            query = """
            MATCH (n:Individual)
            RETURN n.short_form as id, n.label as name, 'ready' as status
            LIMIT 10
            """
            results = vfb.neo_query_wrapper(query)
        
        # Convert to list format
        neurons = []
        for record in results:
            neurons.append({
                'id': record.get('id', f'VFB_test_{len(neurons)+1:03d}'),
                'name': record.get('name', f'Test BANC Neuron {len(neurons)+1}'),
                'status': 'ready'
            })
        
        print(f"Found {len(neurons)} neurons in VFB database")
        return neurons
        
    except Exception as e:
        print(f"Error querying VFB database: {e}")
        print("Creating sample test data...")
        
        # Return test data for development
        return [
            {'id': 'VFB_test_001', 'name': 'Test BANC Neuron 1', 'status': 'ready'},
            {'id': 'VFB_test_002', 'name': 'Test BANC Neuron 2', 'status': 'ready'},
            {'id': 'VFB_test_003', 'name': 'Test BANC Neuron 3', 'status': 'ready'},
        ]

def get_banc_626_skeleton(segment_id, output_dir='banc_output'):
    """
    Download skeleton data for a BANC neuron from the public Google Cloud Storage bucket.
    No authentication required - uses publicly released connectome data.
    """
    try:
        import subprocess
        import tempfile
        
        # BANC public data bucket path
        bucket_path = f"gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_skeletons/swcs-from-pcg-skel/{segment_id}.swc"
        
        print(f"Downloading skeleton for segment ID: {segment_id} from public BANC data...")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Local output path
        swc_file = os.path.join(output_dir, f'{segment_id}.swc')
        
        # Download the skeleton file using gsutil
        result = subprocess.run([
            'gsutil', 'cp', bucket_path, swc_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Skeleton successfully downloaded to: {swc_file}")
            return swc_file
        else:
            print(f"Error downloading skeleton: {result.stderr}")
            # Check if the file exists in the bucket
            check_result = subprocess.run([
                'gsutil', 'ls', bucket_path
            ], capture_output=True, text=True)
            
            if check_result.returncode != 0:
                print(f"Skeleton file {segment_id}.swc not found in BANC public data")
                print("Available neurons can be found at: gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_skeletons/swcs-from-pcg-skel/")
            return None
        
    except Exception as e:
        print(f"Error downloading skeleton: {e}")
        print("Make sure gsutil is installed: brew install google-cloud-sdk")
        return None


def get_banc_annotations(output_dir='banc_output'):
    """
    Download BANC neuron annotation files from the public Google Cloud Storage bucket.
    These contain cell types, proofreading status, and other metadata.
    """
    try:
        import subprocess
        
        print("Downloading BANC neuron annotations from public data...")
        
        # Create output directory if it doesn't exist
        annotations_dir = os.path.join(output_dir, 'annotations')
        os.makedirs(annotations_dir, exist_ok=True)
        
        # Key annotation files to download
        annotation_files = [
            'codex_annotations.parquet',  # Most comprehensive - includes cell types
            'cell_info.parquet',          # General cell information
            'backbone_proofread.parquet', # Proofreading status
            'cell_representative_point.parquet'  # Representative points for each cell
        ]
        
        downloaded_files = {}
        
        for filename in annotation_files:
            bucket_path = f"gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_annotations/v626/{filename}"
            local_path = os.path.join(annotations_dir, filename)
            
            result = subprocess.run([
                'gsutil', 'cp', bucket_path, local_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"Downloaded: {filename}")
                downloaded_files[filename.replace('.parquet', '')] = local_path
            else:
                print(f"Error downloading {filename}: {result.stderr}")
        
        return downloaded_files
        
    except Exception as e:
        print(f"Error downloading annotations: {e}")
        return {}


def get_banc_neuron_info(segment_id, annotations_dir=None):
    """
    Get information about a BANC neuron from the annotation files.
    Returns cell type, proofreading status, and other metadata.
    """
    try:
        import pandas as pd
        
        if annotations_dir is None:
            annotations_dir = os.path.join('banc_output', 'annotations')
        
        neuron_info = {'segment_id': segment_id}
        
        # Load codex annotations (most comprehensive)
        codex_file = os.path.join(annotations_dir, 'codex_annotations.parquet')
        if os.path.exists(codex_file):
            codex_df = pd.read_parquet(codex_file)
            # Look for this segment ID
            segment_info = codex_df[codex_df['root_id'] == int(segment_id)]
            if not segment_info.empty:
                neuron_info.update({
                    'cell_type': segment_info.iloc[0].get('cell_type', 'Unknown'),
                    'flow': segment_info.iloc[0].get('flow', 'Unknown'),
                    'super_class': segment_info.iloc[0].get('super_class', 'Unknown'),
                    'class': segment_info.iloc[0].get('class', 'Unknown'),
                    'malecnt': segment_info.iloc[0].get('malecnt', 0),
                    'fbbt_id': segment_info.iloc[0].get('fbbt_id', None)
                })
        
        # Check proofreading status
        proofread_file = os.path.join(annotations_dir, 'backbone_proofread.parquet')
        if os.path.exists(proofread_file):
            proofread_df = pd.read_parquet(proofread_file)
            is_proofread = int(segment_id) in proofread_df['root_id'].values
            neuron_info['proofread'] = is_proofread
        
        return neuron_info
        
    except Exception as e:
        print(f"Error getting neuron info: {e}")
        return {'segment_id': segment_id, 'error': str(e)}


def list_available_banc_neurons(limit=100):
    """
    List available BANC neurons from the public data bucket.
    Returns a list of segment IDs that have skeleton data available.
    """
    try:
        import subprocess
        import re
        
        print(f"Listing available BANC neurons (limit: {limit})...")
        
        # List skeleton files in the bucket
        result = subprocess.run([
            'gsutil', 'ls', 
            'gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_skeletons/swcs-from-pcg-skel/'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Extract segment IDs from file paths
            lines = result.stdout.strip().split('\n')
            segment_ids = []
            
            for line in lines[:limit]:  # Limit results
                match = re.search(r'/(\d+)\.swc$', line)
                if match:
                    segment_ids.append(match.group(1))
            
            print(f"Found {len(segment_ids)} available neurons")
            return segment_ids
        else:
            print(f"Error listing neurons: {result.stderr}")
            return []
        
    except Exception as e:
        print(f"Error listing available neurons: {e}")
        return []


def transform_skeleton_coordinates(skeleton, source_space="BANC", target_space="VFB"):
    """
    Transform skeleton coordinates from BANC space to VFB space.
    
    Args:
        skeleton (navis.TreeNeuron): Input skeleton in BANC coordinates
        source_space (str): Source coordinate space
        target_space (str): Target coordinate space
        
    Returns:
        navis.TreeNeuron: Skeleton in VFB coordinate space
    """
    print(f"Transforming coordinates for skeleton {skeleton.id}")
    
    # Create a copy to avoid modifying original
    transformed = skeleton.copy()
    
    # Placeholder transformation (replace with actual BANC->VFB transform)
    # This should be replaced with the real transformation matrix from BANC documentation
    scale_factor = 0.8  # Example scaling
    offset = np.array([100, 100, 50])  # Example offset
    
    # Apply transformation to the node coordinates
    if hasattr(transformed, 'nodes') and 'x' in transformed.nodes.columns:
        # Modify the underlying node DataFrame
        transformed.nodes[['x', 'y', 'z']] = (
            transformed.nodes[['x', 'y', 'z']].values * scale_factor + offset
        )
        
        # Mark as transformed
        transformed.name = f"{transformed.name}_VFB_transformed"
        
    print(f"Applied transformation: scale={scale_factor}, offset={offset}")
    return transformed


def create_vfb_file(skeleton, output_path, neuron_id, metadata=None, formats=['swc', 'json']):
    """
    Create VFB-compatible files from skeleton data in multiple formats.
    
    Args:
        skeleton (navis.TreeNeuron): Processed skeleton
        output_path (str): Base output path (without extension)
        neuron_id (str): Neuron identifier  
        metadata (dict): Additional metadata to include
        formats (list): List of output formats ['swc', 'json', 'obj', 'nrrd']
        
    Returns:
        dict: Dictionary of created file paths by format
    """
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    created_files = {}
    
    # Generate mesh from skeleton for OBJ export
    mesh_neuron = None
    if 'obj' in formats:
        try:
            # Convert skeleton to mesh using navis meshing
            mesh_neuron = navis.conversion.tree2meshneuron(skeleton, 
                                                          tube_points=8,
                                                          radius_scale_factor=1.0,
                                                          warn_missing_radii=False)
            print(f"Generated mesh from skeleton with {len(mesh_neuron.vertices)} vertices")
        except Exception as e:
            print(f"Failed to generate mesh: {e}")
            # Create a simple mesh representation
            mesh_neuron = create_simple_mesh_from_skeleton(skeleton)
    
    # Generate volume for NRRD export  
    voxel_neuron = None
    if 'nrrd' in formats:
        try:
            # Convert skeleton to volume using voxelization
            voxel_neuron = navis.conversion.voxelize(skeleton, pitch=100)  # 100nm voxels
            print(f"Generated volume from skeleton with shape {voxel_neuron.grid.shape}")
        except Exception as e:
            print(f"Failed to generate volume: {e}")
            # Create a simple voxel representation  
            voxel_neuron = create_simple_volume_from_skeleton(skeleton)

    # Create SWC file
    if 'swc' in formats:
        swc_path = output_path.with_suffix('.swc')
        navis.write_swc(skeleton, str(swc_path))
        created_files['swc'] = str(swc_path)
    
    # Create OBJ mesh file
    if 'obj' in formats and mesh_neuron is not None:
        obj_path = output_path.with_suffix('.obj')
        navis.write_mesh(mesh_neuron, str(obj_path), filetype='obj')
        created_files['obj'] = str(obj_path)
        print(f"Created OBJ mesh file: {obj_path}")
    
    # Create NRRD volume file
    if 'nrrd' in formats and voxel_neuron is not None:
        nrrd_path = output_path.with_suffix('.nrrd')
        navis.write_nrrd(voxel_neuron, str(nrrd_path))
        created_files['nrrd'] = str(nrrd_path)
        print(f"Created NRRD volume file: {nrrd_path}")
    
    # Create JSON metadata file
    if 'json' in formats:
        json_path = output_path.with_suffix('.json')
        
        # Enhanced metadata including all formats
        vfb_metadata = {
            'neuron_id': neuron_id,
            'source': 'BANC_626', 
            'processing_date': datetime.now().isoformat(),
            'coordinate_space': 'VFB',
            'formats_created': list(created_files.keys()),
            'skeleton_stats': {
                'total_nodes': len(skeleton.vertices) if hasattr(skeleton, 'vertices') else len(skeleton.nodes),
                'total_branches': len(skeleton.segments) if hasattr(skeleton, 'segments') else 0,
                'soma_present': skeleton.soma is not None
            }
        }
        
        # Add mesh stats if available
        if mesh_neuron is not None:
            vfb_metadata['mesh_stats'] = {
                'vertices': len(mesh_neuron.vertices),
                'faces': len(mesh_neuron.faces),
                'volume': float(mesh_neuron.volume) if hasattr(mesh_neuron, 'volume') else None
            }
            
        # Add volume stats if available  
        if voxel_neuron is not None:
            vfb_metadata['volume_stats'] = {
                'shape': list(voxel_neuron.grid.shape) if hasattr(voxel_neuron, 'grid') else None,
                'voxel_spacing': 100,  # nm
                'units': 'nanometer'
            }
        
        if metadata:
            vfb_metadata.update(metadata)
        
        with open(json_path, 'w') as f:
            json.dump(vfb_metadata, f, indent=2)
        created_files['json'] = str(json_path)
    
    print(f"Created VFB files: {', '.join(created_files.values())}")
    return True, list(created_files.values())


def create_simple_mesh_from_skeleton(skeleton):
    """
    Create a simple mesh representation from skeleton when advanced meshing fails.
    """
    try:
        # Get skeleton coordinates
        if hasattr(skeleton, 'nodes'):
            coords = skeleton.nodes[['x', 'y', 'z']].values
        else:
            coords = skeleton.vertices
            
        # Create a simple tube-like mesh along skeleton segments
        # This is a fallback - in production, use more sophisticated meshing
        radius = 50  # nm
        
        # Create simple spheres at each node and connect them
        vertices = []
        faces = []
        
        for i, coord in enumerate(coords):
            # Add sphere vertices around each skeleton node
            for j in range(8):  # 8 vertices per node for simplicity
                angle = j * 2 * np.pi / 8
                x = coord[0] + radius * np.cos(angle)
                y = coord[1] + radius * np.sin(angle)
                z = coord[2]
                vertices.append([x, y, z])
                
        vertices = np.array(vertices)
        
        # Create simple triangular faces connecting the vertices
        for i in range(len(coords) - 1):
            base_idx = i * 8
            next_idx = (i + 1) * 8
            
            for j in range(8):
                v1 = base_idx + j
                v2 = base_idx + (j + 1) % 8
                v3 = next_idx + j
                v4 = next_idx + (j + 1) % 8
                
                # Create two triangles for each quad
                faces.append([v1, v2, v3])
                faces.append([v2, v4, v3])
        
        faces = np.array(faces)
        
        # Create MeshNeuron
        mesh_neuron = navis.MeshNeuron((vertices, faces), 
                                     id=skeleton.id,
                                     name=f"{skeleton.name}_mesh",
                                     units=skeleton.units)
        return mesh_neuron
        
    except Exception as e:
        print(f"Failed to create simple mesh: {e}")
        return None


def create_simple_volume_from_skeleton(skeleton):
    """
    Create a simple volume representation from skeleton when advanced methods fail.
    """
    try:
        # Get skeleton coordinates
        if hasattr(skeleton, 'nodes'):
            coords = skeleton.nodes[['x', 'y', 'z']].values
        else:
            coords = skeleton.vertices
            
        # Create a simple voxel grid
        spacing = 100  # nm per voxel
        
        # Find bounding box
        min_coords = coords.min(axis=0)
        max_coords = coords.max(axis=0)
        
        # Create grid dimensions
        grid_size = ((max_coords - min_coords) / spacing).astype(int) + 10  # Add padding
        
        # Create empty volume
        volume_data = np.zeros(grid_size, dtype=np.uint8)
        
        # Fill voxels along skeleton path
        for coord in coords:
            # Convert to voxel coordinates
            voxel_coord = ((coord - min_coords) / spacing + 5).astype(int)  # +5 for padding
            
            # Ensure within bounds
            voxel_coord = np.clip(voxel_coord, 0, np.array(grid_size) - 1)
            
            # Set voxel and small neighborhood
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    for dz in range(-1, 2):
                        x, y, z = voxel_coord + [dx, dy, dz]
                        if (0 <= x < grid_size[0] and 
                            0 <= y < grid_size[1] and 
                            0 <= z < grid_size[2]):
                            volume_data[x, y, z] = 255
        
        # Create VoxelNeuron object (simulating navis VoxelNeuron)
        class SimpleVoxelNeuron:
            def __init__(self, grid, units='nm'):
                self.grid = grid
                self.units = units
                
        return SimpleVoxelNeuron(volume_data)
        
    except Exception as e:
        print(f"Failed to create simple volume: {e}")
        return None


# Keep the existing R-related functions for compatibility
def setup_r_environment():
    """
    Setup R environment and install/load required packages for BANC transformation.
    """
    if R_AVAILABLE:
        # Using rpy2
        ro.r('''
        if (!require("bancr", quietly = TRUE)) {
            if (!require("pak", quietly = TRUE)) {
                install.packages("pak")
            }
            pak::pkg_install("flyconnectome/bancr")
        }
        if (!require("nat", quietly = TRUE)) {
            install.packages("nat")
        }
        library(bancr)
        library(nat)
        ''')
    else:
        # Check if R is available via subprocess
        try:
            subprocess.run(['R', '--version'], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("R is not available. Please install R or rpy2.")

def get_local_volume_files(local_folder_path):
    """Get local volume files for BANC processing."""
    file_paths = glob.glob(f'{local_folder_path}volume*')
    file_paths += glob.glob(f'{local_folder_path}thumbnail*')
    return file_paths

# Preserve other existing functions for compatibility
def process_neuron_data(df):
    """
    Process neuron data from a pandas DataFrame.
    This function maintains compatibility with existing code.
    """
    processed_neurons = []
    
    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            # Extract neuron information
            neuron_info = {
                'id': row.get('id', f'neuron_{idx}'),
                'name': row.get('name', f'Neuron {idx}'),
                'x': row.get('x', 0),
                'y': row.get('y', 0), 
                'z': row.get('z', 0)
            }
            
            processed_neurons.append(neuron_info)
            
        except Exception as e:
            print(f"Error processing neuron {idx}: {e}")
            continue
    
    return processed_neurons


def get_vfb_neuron_data(vfb_neuron_id):
    """
    Get detailed metadata for a specific VFB neuron.
    """
    try:
        # VFB database connection parameters
        server = 'kbw.virtualflybrain.org'
        password = os.getenv('password', 'banana2-funky-Earthy-Irvin-Tactful0-felice9')
        
        # Initialize VFB connection
        vfb = VfbConnect(
            neo_endpoint=f'http://{server}:7474',
            neo_credentials=('neo4j', password)
        )
        
        # Query for specific neuron data
        query = f"""
        MATCH (n:Individual {{short_form: '{vfb_neuron_id}'}})
        RETURN n.short_form as id, n.label as label, n.description as description
        """
        
        results = vfb.neo_query_wrapper(query)
        
        if results:
            record = results[0]
            return {
                'id': record.get('id', vfb_neuron_id),
                'label': record.get('label', f'VFB Neuron {vfb_neuron_id}'),
                'description': record.get('description', ''),
                'source': 'VFB'
            }
        else:
            # Return mock data for testing
            return {
                'id': vfb_neuron_id,
                'label': f'VFB Neuron {vfb_neuron_id}',
                'description': f'Test neuron for {vfb_neuron_id}',
                'source': 'VFB'
            }
        
    except Exception as e:
        print(f"Error getting VFB neuron data: {e}")
        # Return mock data
        return {
            'id': vfb_neuron_id,
            'label': f'VFB Neuron {vfb_neuron_id}',
            'description': f'Test neuron for {vfb_neuron_id}',
            'source': 'VFB'
        }


def load_skeleton(skeleton_file):
    """
    Load skeleton from SWC file using navis.
    """
    try:
        import navis
        
        # Load SWC file
        skeleton = navis.read_swc(skeleton_file)
        
        if isinstance(skeleton, navis.TreeNeuron):
            print(f"Loaded skeleton with {len(skeleton.nodes)} nodes")
            return skeleton
        else:
            print("Error: Loaded object is not a TreeNeuron")
            return None
    
    except Exception as e:
        print(f"Error loading skeleton: {e}")
        return None


def process_vfb_neuron_with_banc_data(vfb_neuron_id, banc_segment_id=None, output_dir='banc_vfb_output', formats=['swc', 'json']):
    """
    Complete workflow: Get VFB neuron metadata, download BANC data, align to templates, create VFB formats.
    
    Args:
        vfb_neuron_id: VFB neuron identifier
        banc_segment_id: BANC segment ID (if None, will try to find mapping)
        output_dir: Output directory for processed files
        formats: List of output formats ['swc', 'json', 'obj', 'nrrd']
    
    Returns:
        dict: Processing results and file paths
    """
    results = {
        'vfb_id': vfb_neuron_id,
        'banc_segment_id': banc_segment_id,
        'success': False,
        'files': {},
        'errors': []
    }
    
    try:
        print(f"\n=== Processing VFB neuron {vfb_neuron_id} ===")
        
        # Step 1: Get VFB metadata
        print("Step 1: Getting VFB neuron metadata...")
        vfb_data = get_vfb_neuron_data(vfb_neuron_id)
        if not vfb_data:
            results['errors'].append("Failed to get VFB neuron data")
            return results
        
        results['vfb_metadata'] = vfb_data
        print(f"Found VFB neuron: {vfb_data.get('label', 'Unknown')}")
        
        # Step 2: Find BANC mapping if not provided
        if banc_segment_id is None:
            print("Step 2: Looking for VFB->BANC mapping...")
            # TODO: Implement mapping logic based on cell type/annotation matching
            # For now, we'll need the BANC ID to be provided
            results['errors'].append("BANC segment ID must be provided - automated mapping not yet implemented")
            return results
        
        print(f"Using BANC segment ID: {banc_segment_id}")
        
        # Step 3: Download BANC annotations
        print("Step 3: Downloading BANC annotations...")
        annotation_files = get_banc_annotations(output_dir)
        if annotation_files:
            print(f"Downloaded {len(annotation_files)} annotation files")
        
        # Step 4: Get BANC neuron info
        print("Step 4: Getting BANC neuron information...")
        banc_info = get_banc_neuron_info(banc_segment_id, 
                                       os.path.join(output_dir, 'annotations'))
        results['banc_metadata'] = banc_info
        print(f"BANC neuron type: {banc_info.get('cell_type', 'Unknown')}")
        
        # Step 5: Download BANC skeleton
        print("Step 5: Downloading BANC skeleton data...")
        skeleton_file = get_banc_626_skeleton(banc_segment_id, output_dir)
        if not skeleton_file:
            results['errors'].append("Failed to download BANC skeleton")
            return results
        
        # Step 6: Load and transform skeleton
        print("Step 6: Loading and transforming skeleton...")
        skeleton = load_skeleton(skeleton_file)
        if skeleton is None:
            results['errors'].append("Failed to load skeleton")
            return results
        
        # Step 7: Coordinate transformation (BANC -> JRC2018U)
        print("Step 7: Transforming coordinates to JRC2018U template...")
        # For now, using identity transform - need proper BANC->JRC2018U mapping
        transformed_skeleton = skeleton.copy()
        # TODO: Implement proper coordinate transformation
        print("Warning: Using identity transform - proper BANC->JRC2018U transform needed")
        
        # Step 8: Create VFB output files
        print("Step 8: Creating VFB output files...")
        output_base = f"VFB_{vfb_neuron_id}_BANC_{banc_segment_id}"
        
        output_files = create_vfb_file(
            transformed_skeleton, 
            vfb_data,
            output_base, 
            output_dir, 
            formats
        )
        
        if output_files:
            results['files'] = output_files
            results['success'] = True
            print(f"Successfully created {len(output_files)} output files")
            for format_type, filepath in output_files.items():
                print(f"  {format_type.upper()}: {filepath}")
        else:
            results['errors'].append("Failed to create output files")
        
        return results
        
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        print(error_msg)
        results['errors'].append(error_msg)
        return results
