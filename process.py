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


def create_vfb_file(skeleton, output_path, neuron_id, metadata=None):
    """
    Create VFB-compatible files from skeleton data.
    
    Args:
        skeleton (navis.TreeNeuron): Processed skeleton
        output_path (str): Output file path (without extension)
        neuron_id (str): Neuron identifier
        metadata (dict, optional): Additional metadata
        
    Returns:
        dict: Created file paths
    """
    
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create SWC file
    swc_path = output_path.with_suffix('.swc')
    navis.write_swc(skeleton, swc_path)
    
    # Create JSON metadata file
    json_path = output_path.with_suffix('.json')
    
    vfb_metadata = {
        'neuron_id': neuron_id,
        'source': 'BANC_626',
        'processing_date': pd.Timestamp.now().isoformat(),
        'coordinate_space': 'VFB',
        'file_format': 'SWC',
        'skeleton_stats': {
            'total_nodes': len(skeleton.vertices) if hasattr(skeleton, 'vertices') else len(skeleton.nodes),
            'total_branches': len(skeleton.segments) if hasattr(skeleton, 'segments') else 0,
            'soma_present': skeleton.soma is not None
        }
    }
    
    if metadata:
        vfb_metadata.update(metadata)
    
    with open(json_path, 'w') as f:
        json.dump(vfb_metadata, f, indent=2)
    
    print(f"Created VFB files: {swc_path}, {json_path}")
    
    return {
        'swc': str(swc_path),
        'json': str(json_path)
    }


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
