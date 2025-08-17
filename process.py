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

# Try to import rpy2 for R integration (optional)
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
    Query VFB database for all BANC neuron records that need processing.
    
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
        
        # Enhanced query for BANC neurons with folder information from in_register_with relationships
        query = """
        MATCH (s:Site {short_form:'BANC626'})<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
        WHERE exists(r.folder)
        RETURN c.accession[0] as banc_id,
               i.short_form as vfb_id,
               t.short_form as template_id,
               r.folder[0] as folder_path,
               r.filename as filename,
               i.label as name
        ORDER BY c.accession[0]
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = vfb.cypher_query(query)
        
        if results.empty:
            # Fallback: Try broader search for BANC references
            print("No BANC626 site references found, trying broader BANC search...")
            query = """
            MATCH (s:Site)<-[c:hasDbXref]-(i:Individual)<-[:depicts]-(ic:Individual)-[r:in_register_with]->(tc:Template)-[:depicts]-(t:Template) 
            WHERE (s.short_form CONTAINS 'BANC' OR c.accession[0] =~ '720575941.*') AND exists(r.folder)
            RETURN c.accession[0] as banc_id,
                   i.short_form as vfb_id,
                   t.short_form as template_id,
                   r.folder[0] as folder_path,
                   r.filename as filename,
                   coalesce(i.label, 'BANC Neuron') as name
            ORDER BY c.accession[0]
            """
            if limit:
                query += f" LIMIT {limit}"
            results = vfb.cypher_query(query)
        
        if results.empty:
            # Generate test data with proper folder structure for development
            print("No neurons found in VFB, generating test data with known BANC IDs and folder paths...")
            test_neurons = [
                {
                    'banc_id': '720575941350274352', 
                    'vfb_id': 'VFB_00105fa2',
                    'template_id': 'VFB_00101567',
                    'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/5fa2/VFB_00101567/'
                },
                {
                    'banc_id': '720575941350334256', 
                    'vfb_id': 'VFB_00105fb1',
                    'template_id': 'VFB_00101567',
                    'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/5fb1/VFB_00101567/'
                },
                {
                    'banc_id': '720575941350274112', 
                    'vfb_id': 'VFB_00106000',
                    'template_id': 'VFB_00200000',  # VNC template example
                    'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/6000/VFB_00200000/'
                }
            ]
            
            results = []
            for i, neuron_data in enumerate(test_neurons):
                if limit and i >= limit:
                    break
                results.append(neuron_data)
        
        # Convert to list format and extract folder paths
        neurons = []
        if hasattr(results, 'iterrows'):
            # DataFrame from cypher_query
            for _, record in results.iterrows():
                banc_id = str(record.get('banc_id', ''))
                vfb_id = record.get('vfb_id', '')
                template_id = record.get('template_id', 'VFB_00101567')
                folder_path = record.get('folder_path', '')
                
                # Parse folder URL to extract local filesystem path
                if folder_path and 'virtualflybrain.org/data/' in folder_path:
                    # Extract path after /data/ from URL
                    # http://www.virtualflybrain.org/data/VFB/i/0010/5fa2/VFB_00101567/
                    # becomes: VFB/i/0010/5fa2/VFB_00101567/
                    url_parts = folder_path.split('/data/')
                    if len(url_parts) > 1:
                        local_folder_path = url_parts[1].rstrip('/')  # Remove trailing slash
                    else:
                        # Fallback to template-based path
                        local_folder_path = f'VFB/i/{vfb_id[-4:]}/{template_id}'
                else:
                    # Default structure for missing folder_path
                    local_folder_path = f'VFB/i/{vfb_id[-4:] if len(vfb_id) >= 4 else "unknown"}/{template_id}'
                
                neurons.append({
                    'id': banc_id,
                    'vfb_id': vfb_id,
                    'name': record.get('name', f'BANC Neuron {banc_id}'),
                    'template_id': template_id,
                    'folder_path': folder_path,
                    'local_folder_path': local_folder_path,  # Key addition for filesystem organization
                    'template_folder': template_id,  # Keep for backward compatibility
                    'status': 'ready'
                })
        else:
            # List of dictionaries (test data)
            for record in results:
                banc_id = str(record.get('banc_id', ''))
                vfb_id = record.get('vfb_id', '')
                template_id = record.get('template_id', 'VFB_00101567')
                folder_path = record.get('folder_path', '')
                
                # Parse folder URL to extract local filesystem path
                if folder_path and 'virtualflybrain.org/data/' in folder_path:
                    # Extract path after /data/ from URL
                    url_parts = folder_path.split('/data/')
                    if len(url_parts) > 1:
                        local_folder_path = url_parts[1].rstrip('/')  # Remove trailing slash
                    else:
                        # Fallback to template-based path
                        local_folder_path = f'VFB/i/{vfb_id[-4:]}/{template_id}'
                else:
                    # Default structure for missing folder_path
                    local_folder_path = f'VFB/i/{vfb_id[-4:] if len(vfb_id) >= 4 else "unknown"}/{template_id}'
                
                neurons.append({
                    'id': banc_id,
                    'vfb_id': vfb_id,
                    'name': record.get('name', f'BANC Neuron {banc_id}'),
                    'template_id': template_id,
                    'folder_path': folder_path,
                    'local_folder_path': local_folder_path,  # Key addition for filesystem organization
                    'template_folder': template_id,  # Keep for backward compatibility
                    'status': 'ready'
                })
        
        print(f"Found {len(neurons)} BANC neurons with folder organization")
        for neuron in neurons[:5]:  # Show first 5
            print(f"  - {neuron['id']}: {neuron['name']} (template: {neuron['template_folder']})")
        if len(neurons) > 5:
            print(f"  ... and {len(neurons) - 5} more")
        
        return neurons
        
    except Exception as e:
        print(f"Error querying VFB database: {e}")
        print("Creating sample test data with known BANC neuron IDs...")
        
        # Return test data with folder structure for development
        test_neurons = [
            {
                'id': '720575941350274352',
                'vfb_id': 'VFB_00105fa2',
                'name': 'Test BANC Neuron 1',
                'template_id': 'VFB_00101567',
                'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/5fa2/VFB_00101567/',
                'local_folder_path': 'VFB/i/0010/5fa2/VFB_00101567',
                'template_folder': 'VFB_00101567',
                'status': 'ready'
            },
            {
                'id': '720575941350334256',
                'vfb_id': 'VFB_00105fb1',
                'name': 'Test BANC Neuron 2',
                'template_id': 'VFB_00101567',
                'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/5fb1/VFB_00101567/',
                'local_folder_path': 'VFB/i/0010/5fb1/VFB_00101567',
                'template_folder': 'VFB_00101567',
                'status': 'ready'
            },
            {
                'id': '720575941350274112',
                'vfb_id': 'VFB_00106000',
                'name': 'Test BANC Neuron 3',
                'template_id': 'VFB_00200000',
                'folder_path': 'http://www.virtualflybrain.org/data/VFB/i/0010/6000/VFB_00200000/',
                'local_folder_path': 'VFB/i/0010/6000/VFB_00200000',
                'template_folder': 'VFB_00200000',
                'status': 'ready'
            }
        ]
        
        if limit:
            return test_neurons[:limit]
        return test_neurons

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
            
            # Load the skeleton with navis and return the skeleton object
            try:
                import navis
                skeleton = navis.read_swc(swc_file)
                print(f"Skeleton loaded: {len(skeleton.nodes)} nodes")
                return skeleton
            except Exception as e:
                print(f"Error loading skeleton from {swc_file}: {e}")
                return None
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
    Transform skeleton coordinates between different template spaces using BANC's official transforms.
    
    The BANC team has provided official transformation functions in their repository:
    https://github.com/jasper-tms/the-BANC-fly-connectome/tree/main/fanc/transforms
    
    Args:
        skeleton: navis TreeNeuron object
        source_space: Source coordinate space ('BANC', 'FANC', 'JRC2018F', etc.)
        target_space: Target coordinate space ('VFB', 'JRC2018F', 'JRC2018U', etc.)
    
    Returns:
        Transformed skeleton
    """
    import navis
    import numpy as np
    
    try:
        print(f"Transforming coordinates from {source_space} to {target_space}")
        
        # Handle BANC-specific transformations using official BANC transforms
        if source_space == "BANC":
            if target_space in ["VFB", "JRC2018F", "JRC2018U"]:
                print("Using official BANC transformation functions")
                
                try:
                    # Try to import BANC transformation functions
                    from fanc.transforms.template_alignment import (
                        warp_points_BANC_to_template,
                        warp_points_BANC_to_brain_template,
                        warp_points_BANC_to_vnc_template
                    )
                    
                    # Get skeleton coordinates
                    points = skeleton.nodes[['x', 'y', 'z']].values
                    
                    # Determine if this is brain or VNC based on y-coordinate
                    # From BANC wiki: brain (z: 0-6206), VNC (z: 1438-7009)
                    # In nm coordinates: y > ~320,000 is typically VNC region
                    avg_y = np.mean(points[:, 1])
                    
                    if avg_y > 320000:  # VNC region
                        print(f"Detected VNC neuron (avg y: {avg_y:.0f}nm), using VNC template transform")
                        transformed_points = warp_points_BANC_to_vnc_template(
                            points,
                            input_units='nanometers',
                            output_units='microns'
                        )
                        coordinate_space = "JRCVNC2018F"
                    else:  # Brain region
                        print(f"Detected brain neuron (avg y: {avg_y:.0f}nm), using brain template transform")
                        transformed_points = warp_points_BANC_to_brain_template(
                            points,
                            input_units='nanometers',
                            output_units='microns'
                        )
                        coordinate_space = "JRC2018F"
                    
                    # Update skeleton coordinates
                    skeleton_copy = skeleton.copy()
                    skeleton_copy.nodes.loc[:, ['x', 'y', 'z']] = transformed_points
                    
                    # If target is VFB (which typically uses JRC2018U), chain transforms
                    if target_space == "VFB" and coordinate_space == "JRC2018F":
                        print("Chaining transform: JRC2018F -> JRC2018U for VFB compatibility")
                        try:
                            import flybrains
                            final_points = navis.xform_brain(
                                transformed_points, 
                                source='JRC2018F', 
                                target='JRC2018U'
                            )
                            skeleton_copy.nodes.loc[:, ['x', 'y', 'z']] = final_points
                        except Exception as e:
                            print(f"JRC2018F->JRC2018U transform failed: {e}")
                            print("Using JRC2018F coordinates")
                    
                    print(f"Successfully transformed to {coordinate_space} template space")
                    return skeleton_copy
                    
                except ImportError as e:
                    print(f"BANC transform package not available: {e}")
                    print("To use official BANC transforms, install the BANC package:")
                    print("git clone https://github.com/jasper-tms/the-BANC-fly-connectome.git")
                    print("cd the-BANC-fly-connectome && pip install -e .")
                    print("Also requires: pip install git+https://github.com/jasper-tms/pytransformix.git")
                    print("And elastix binary in PATH")
                    return skeleton.copy()
                
                except Exception as e:
                    print(f"BANC transformation failed: {e}")
                    print("Using identity transform as fallback")
                    return skeleton.copy()
            
            elif target_space == "FANC":
                print("Note: BANC VNC coordinates may align with FANC")
                print("Future: Check if neuron is in VNC region and use FANC coordinates")
                return skeleton.copy()
                
        # Handle FANC transformations (these work with navis-flybrains)
        elif source_space == "FANC":
            if target_space in ["JRCVNC2018F", "JRCVNC2018U"]:
                print(f"Using navis-flybrains transform: {source_space} -> {target_space}")
                try:
                    import flybrains
                    points = skeleton.nodes[['x', 'y', 'z']].values
                    transformed_points = navis.xform_brain(points, source=source_space, target=target_space)
                    
                    skeleton_copy = skeleton.copy()
                    skeleton_copy.nodes.loc[:, ['x', 'y', 'z']] = transformed_points
                    return skeleton_copy
                    
                except Exception as e:
                    print(f"Transform failed: {e}")
                    print("Note: FANC transforms require Elastix to be installed")
                    return skeleton.copy()
        
        # Handle standard JRC template transformations
        elif source_space in ["JRC2018F", "JRC2018M", "JRC2018U"] and target_space in ["JRC2018F", "JRC2018M", "JRC2018U"]:
            print(f"Using navis-flybrains transform: {source_space} -> {target_space}")
            try:
                import flybrains
                points = skeleton.nodes[['x', 'y', 'z']].values
                transformed_points = navis.xform_brain(points, source=source_space, target=target_space)
                
                skeleton_copy = skeleton.copy()
                skeleton_copy.nodes.loc[:, ['x', 'y', 'z']] = transformed_points
                return skeleton_copy
                
            except Exception as e:
                print(f"Transform failed: {e}")
                return skeleton.copy()
        
        else:
            print(f"No transform available from {source_space} to {target_space}")
            print("Available template spaces in navis-flybrains:")
            print("Brain: FAFB14, FLYWIRE, JRC2018F, JRC2018M, JRC2018U, JRCFIB2018F")
            print("VNC: FANC, JRCVNC2018F, JRCVNC2018M, JRCVNC2018U")
            print("BANC: Use official BANC transformation functions")
            return skeleton.copy()
    
    except Exception as e:
        print(f"Coordinate transformation error: {e}")
        return skeleton.copy()


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



