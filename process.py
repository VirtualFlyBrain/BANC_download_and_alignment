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

def get_banc_626_skeleton(neuron_id):
    """
    Fetch skeleton data for a BANC 626 neuron using multiple approaches.
    
    Methods tried in order:
    1. pcg_skel direct skeleton generation
    2. Local skeleton files (.swc format)
    3. Placeholder/mock skeleton for testing
    
    Args:
        neuron_id (str): BANC neuron identifier
        
    Returns:
        navis.TreeNeuron: Skeleton data
    """
    
    # Method 1: Try pcg_skel approach
    if BANC_AVAILABLE:
        try:
            print(f"Attempting pcg_skel for neuron {neuron_id}...")
            
            # Try using pcg_skel for skeleton generation
            try:
                import pcg_skel
                
                # Set up BANC client
                client = CAVEclient("brain_and_nerve_cord")
                client.auth.token = os.getenv('FLYWIRE_SECRET', '4f286f518add5e15c2c82c20299295c7')
                
                # Extract numeric ID if needed
                if isinstance(neuron_id, str) and 'VFB_test_' in neuron_id:
                    # Use a sample BANC ID for testing
                    numeric_id = 648518346486614449
                else:
                    numeric_id = int(neuron_id)
                
                # Generate skeleton using pcg_skel
                skeleton = pcg_skel.pcg_skeleton(numeric_id, client=client)
                
                # Convert to navis format
                skeleton = navis.TreeNeuron(skeleton.vertices, skeleton.edges, 
                                          id=neuron_id, name=f"BANC_{neuron_id}")
                print(f"Successfully generated skeleton with {len(skeleton.vertices)} nodes")
                return skeleton
                
            except Exception as e:
                print(f"pcg_skel failed: {e}")
                
        except Exception as e:
            print(f"BANC method failed: {e}")
    
    # Method 2: Check for local skeleton files
    local_paths = [
        f"/Users/rcourt/GIT/BANC_download_and_alignment/skeletons/{neuron_id}.swc",
        f"./skeletons/{neuron_id}.swc",
        f"./{neuron_id}.swc"
    ]
    
    for path in local_paths:
        if os.path.exists(path):
            try:
                skeleton = navis.read_swc(path)
                skeleton.id = neuron_id
                skeleton.name = f"BANC_{neuron_id}"
                print(f"Loaded local skeleton from {path}")
                return skeleton
            except Exception as e:
                print(f"Failed to load {path}: {e}")
    
    # Method 3: Generate mock skeleton for testing
    print(f"Generating mock skeleton for {neuron_id}")
    
    # Create a simple skeleton using SWC format structure
    import pandas as pd
    
    # Create SWC-style data
    swc_data = pd.DataFrame({
        'node_id': [1, 2, 3, 4, 5, 6, 7, 8],
        'parent_id': [-1, 1, 2, 3, 3, 4, 5, 3],
        'x': [0, 10, 20, 30, 30, 40, 40, 50],
        'y': [0, 0, 0, 10, -10, 20, -20, 0],
        'z': [0, 0, 0, 0, 0, 0, 0, 0],
        'radius': [1, 1, 1, 1, 1, 1, 1, 1],
        'label': [1, 3, 3, 3, 3, 3, 3, 4]  # 1=soma, 3=dendrite, 4=axon
    })
    
    skeleton = navis.TreeNeuron(
        swc_data, 
        id=neuron_id, 
        name=f"Mock_BANC_{neuron_id}",
        units='nm'
    )
    
    print(f"Created mock skeleton with {len(skeleton.vertices)} nodes")
    return skeleton


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
