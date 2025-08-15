#!/usr/bin/env python3

import os
import glob
import navis
import flybrains
import pandas as pd
import numpy as np
import subprocess
import tempfile
from pathlib import Path
from vfb_connect.cross_server_tools import VfbConnect
from concurrent.futures import ThreadPoolExecutor, as_completed
from fafbseg import flywire  # flywire package now supports BANC through dataset='banc' parameter

# Try to import rpy2 for R integration
try:
    import rpy2.robjects as ro
    from rpy2.robjects import pandas2ri
    from rpy2.robjects.packages import importr
    pandas2ri.activate()
    R_AVAILABLE = True
except ImportError:
    print("Warning: rpy2 not installed. Will use subprocess to call R.")
    R_AVAILABLE = False

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
            raise RuntimeError("R is not installed or not in PATH. Please install R and the bancr package.")

def delete_volume_files(local_folder_path):
    """
    Delete all files matching the pattern "volume.*" in the specified folder.
    :param local_folder_path: str, path to the folder containing the files to delete
    """
    if not local_folder_path.endswith(os.sep):
        local_folder_path += os.sep
    file_paths = glob.glob(f'{local_folder_path}volume*')
    file_paths += glob.glob(f'{local_folder_path}thumbnail*')
    for file_path in file_paths:
        try:
            os.remove(file_path)
            print(f'Successfully deleted {file_path}')
        except Exception as e:
            print(f'Could not delete {file_path}: {e}')

def detect_neuron_primary_region(neuron_data):
    """
    Detect the primary region (brain or VNC) for a neuron based on its extent.
    Many neurons span both regions (e.g., DNs and ANs), so we determine the primary region
    based on where most of the neuron is located.
    
    :param neuron_data: navis neuron object
    :return: tuple of ('brain' or 'vnc', span_ratio)
    """
    if hasattr(neuron_data, 'nodes'):
        # Safely access z coordinates
        if 'z' in neuron_data.nodes.columns:
            z_coords = neuron_data.nodes['z'].values
        elif len(neuron_data.nodes.columns) >= 3:
            z_coords = neuron_data.nodes.iloc[:, 2].values  # Third column as z
        else:
            print("Warning: Cannot find z coordinates in neuron data")
            return 'brain', 1.0
        
        # These thresholds are approximate and may need adjustment based on BANC coordinates
        # The brain-VNC boundary is roughly around Z=150000 nm in BANC space
        VNC_BRAIN_BOUNDARY = 150000  # in nanometers
        
        # Calculate what fraction is in each region
        vnc_nodes = np.sum(z_coords < VNC_BRAIN_BOUNDARY)
        brain_nodes = np.sum(z_coords >= VNC_BRAIN_BOUNDARY)
        total_nodes = len(z_coords)
        
        brain_ratio = brain_nodes / total_nodes if total_nodes > 0 else 0.5
        
        # Determine primary region based on majority
        if brain_ratio > 0.6:
            return 'brain', brain_ratio
        elif brain_ratio < 0.4:
            return 'vnc', 1 - brain_ratio
        else:
            # Neuron spans both regions significantly
            # Default to brain for DNs (which typically have soma in brain)
            # This could be refined based on neuron type if available
            return 'brain', brain_ratio
    else:
        return 'brain', 1.0

def transform_banc_to_jrc2018f(neuron_data, temp_dir, force_region=None):
    """
    Transform BANC neuron data to JRC2018F using R bancr package.
    The bancr package handles both brain and VNC regions appropriately.
    
    :param neuron_data: navis neuron object
    :param temp_dir: temporary directory for intermediate files
    :param force_region: Optional - force transformation for specific region ('brain' or 'vnc')
    :return: tuple of (brain_transformed, vnc_transformed, primary_region)
    """
    # Detect primary region if not forced
    if force_region:
        primary_region = force_region
        print(f"     Forced region: {primary_region}")
    else:
        primary_region, ratio = detect_neuron_primary_region(neuron_data)
        print(f"     Primary region: {primary_region} ({ratio:.1%} of neuron)")
    
    # Save neuron data to temporary file
    temp_input = os.path.join(temp_dir, "temp_neuron.swc")
    
    # Save the neuron to SWC format
    navis.write_swc(neuron_data, temp_input)
    
    # Transform for both regions if neuron spans both
    # The bancr package handles this appropriately
    transformed_neurons = {}
    
    for region in ['brain', 'vnc']:
        temp_output = os.path.join(temp_dir, f"temp_neuron_{region}.swc")
        
        try:
            if R_AVAILABLE:
                # Use rpy2 to transform
                ro.r(f'''
                library(bancr)
                library(nat)
                
                # Read the neuron
                n <- read.neuron("{temp_input}")
                
                # Transform from BANC to JRC2018F for specific region
                # The region parameter tells bancr which template to use
                n_transformed <- banc_to_JRC2018F(n, region="{region.upper()}")
                
                # Save the transformed neuron
                write.neuron(n_transformed, "{temp_output}", format="swc")
                ''')
            else:
                # Use subprocess to call R script
                r_script = f'''
                library(bancr)
                library(nat)
                
                # Read the neuron
                n <- read.neuron("{temp_input}")
                
                # Transform from BANC to JRC2018F for {region}
                n_transformed <- banc_to_JRC2018F(n, region="{region.upper()}")
                
                # Save the transformed neuron
                write.neuron(n_transformed, "{temp_output}", format="swc")
                '''
                
                # Write R script to file
                r_script_file = os.path.join(temp_dir, f"transform_{region}.R")
                with open(r_script_file, 'w') as f:
                    f.write(r_script)
                
                # Execute R script
                result = subprocess.run(['Rscript', r_script_file], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"R script error for {region}: {result.stderr}")
                    transformed_neurons[region] = None
                    continue
            
            # Read the transformed neuron back
            if os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                transformed_neurons[region] = navis.read_swc(temp_output)
                os.remove(temp_output)
            else:
                transformed_neurons[region] = None
                
        except Exception as e:
            print(f"     Warning: Failed to transform for {region}: {e}")
            transformed_neurons[region] = None
    
    # Clean up temporary input file
    os.remove(temp_input)
    
    return transformed_neurons.get('brain'), transformed_neurons.get('vnc'), primary_region

def process_banc_neuron(body_id, folder_url):
    """
    Process each BANC neuron to download and transform data, then save the required files.
    Handles neurons that may span both brain and VNC, saving to appropriate template folders.
    
    Folder structure: /VFB/i/[first_4_digits]/[next_4_digits]/[template_short_form]/
    
    :param body_id: int, ID of the neuron to process
    :param folder_url: str, URL of the folder where the data is stored
    """
    # Template short_form IDs mapping
    TEMPLATE_IDS = {
        'JRC2018U': 'VFB_00101567',          # JRC2018Unisex (brain)
        'JRC2018VNCunisex': 'VFB_00200000',  # JRC2018UnisexVNC
        'JRCVNC2018U': 'VFB_00200000',       # Alternative VNC name
    }
    
    print(f"Processing neuron {body_id}...")
    
    # Parse the base folder path from the URL
    # Expected format: http://www.virtualflybrain.org/data/VFB/i/####/####/template_short_form/
    base_url = folder_url.replace('http://www.virtualflybrain.org/data/', '')
    
    # Extract the VFB neuron path structure (without template)
    # Example: VFB/i/1234/5678/VFB_00101567/ -> VFB/i/1234/5678/
    path_parts = base_url.rstrip('/').split('/')
    
    # The structure should be: VFB/i/####/####/[template_short_form]
    # We want to keep everything except the template part
    if len(path_parts) >= 5 and path_parts[0] == 'VFB' and path_parts[1] == 'i':
        # Keep the base path: VFB/i/####/####/
        base_neuron_path = '/'.join(path_parts[:4])  # VFB/i/####/####
    else:
        # Fallback if structure is unexpected
        print(f"Warning: Unexpected folder structure: {folder_url}")
        base_neuron_path = base_url.rstrip('/').rsplit('/', 1)[0] if '/' in base_url else base_url
    
    # Create temporary directory for R transformations
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Get skeleton from BANC using flywire package with dataset='banc'
            neuron = flywire.get_skeletons(body_id, dataset='banc')
            
            if neuron is None:
                print(f"Warning: Could not retrieve skeleton for neuron {body_id}")
                return
            
            # Transform: BANC -> JRC2018F (using R) for both brain and VNC
            brain_jrc2018f, vnc_jrc2018f, primary_region = transform_banc_to_jrc2018f(neuron, temp_dir)
            
            # Track which templates were successfully transformed to
            transformed_templates = {}
            
            # Process brain transformation if available
            if brain_jrc2018f is not None:
                try:
                    # Transform: JRC2018F -> JRC2018U (brain template)
                    brain_final = navis.xform_brain(brain_jrc2018f, source='JRC2018F', target='JRC2018U')
                    if brain_final:
                        transformed_templates['JRC2018U'] = brain_final
                        print(f"     ✓ Brain transformation successful (JRC2018U)")
                except Exception as e:
                    print(f"     Warning: Brain transformation to JRC2018U failed: {e}")
            
            # Process VNC transformation if available
            if vnc_jrc2018f is not None:
                try:
                    # Try VNC-specific template first
                    try:
                        vnc_final = navis.xform_brain(vnc_jrc2018f, source='JRC2018F', target='JRC2018VNCunisex')
                        vnc_template_name = 'JRC2018VNCunisex'
                    except:
                        # Fallback to alternative VNC template name
                        try:
                            vnc_final = navis.xform_brain(vnc_jrc2018f, source='JRC2018F', target='JRCVNC2018U')
                            vnc_template_name = 'JRCVNC2018U'
                        except:
                            # Final fallback to unified template
                            vnc_final = navis.xform_brain(vnc_jrc2018f, source='JRC2018F', target='JRC2018U')
                            vnc_template_name = 'JRC2018U'
                    
                    if vnc_final:
                        transformed_templates[vnc_template_name] = vnc_final
                        print(f"     ✓ VNC transformation successful ({vnc_template_name})")
                except Exception as e:
                    print(f"     Warning: VNC transformation failed: {e}")
            
            # Now save to appropriate template folders
            if not transformed_templates:
                print(f"Warning: No successful transformations for neuron {body_id}")
                return
            
            # Determine primary template based on primary region
            if primary_region == 'brain' and 'JRC2018U' in transformed_templates:
                primary_template = 'JRC2018U'
            elif primary_region == 'vnc':
                # Use whichever VNC template succeeded
                vnc_templates = [k for k in transformed_templates.keys() if 'VNC' in k.upper()]
                primary_template = vnc_templates[0] if vnc_templates else 'JRC2018U'
            else:
                # Use first available template
                primary_template = list(transformed_templates.keys())[0]
            
            # Save to each template's folder
            for template_name, transformed_neuron in transformed_templates.items():
                # Get template short_form ID
                template_id = TEMPLATE_IDS.get(template_name, template_name)
                
                # Construct folder path: /IMAGE_WRITE/VFB/i/####/####/template_short_form/
                local_folder_path = f"/IMAGE_WRITE/{base_neuron_path}/{template_id}/"
                os.makedirs(local_folder_path, exist_ok=True)
                
                # Define file paths
                swc_filename = os.path.join(local_folder_path, "volume.swc")
                
                # Check if we should skip or redo
                if os.path.exists(swc_filename):
                    if os.environ.get('redo', '').lower() == 'true':
                        print(f"     Removing old files in {local_folder_path}...")
                        delete_volume_files(local_folder_path)
                    else:
                        print(f"     Files already exist in {local_folder_path}, skipping...")
                        continue
                
                # Save SWC file
                navis.write_swc(transformed_neuron, swc_filename)
                web_url = f"http://www.virtualflybrain.org/data/{base_neuron_path}/{template_id}/volume.swc"
                print(f"     Saved to {template_id}: {web_url}")
                
                # For primary template only, also save mesh and NRRD
                if template_name == primary_template:
                    # Process mesh
                    try:
                        mesh_filename = os.path.join(local_folder_path, "volume_man.obj")
                        if not os.path.exists(mesh_filename) or os.path.getsize(mesh_filename) < 1000:
                            mesh_neuron = flywire.get_mesh_neuron(body_id, dataset='banc', lod=2)
                            
                            if mesh_neuron is not None:
                                # Simple transformation for mesh (could be improved)
                                mesh_transformed = navis.xform_brain(mesh_neuron, source='BANC', target=template_name)
                                
                                if mesh_transformed:
                                    try:
                                        navis.write_mesh(mesh_transformed, mesh_filename)
                                        print(f"     Mesh saved: {mesh_filename.replace('/IMAGE_WRITE/', 'http://www.virtualflybrain.org/data/')}")
                                    except AttributeError:
                                        print(f"     Warning: navis.write_mesh not available, skipping mesh for {body_id}")
                                    except Exception as e:
                                        print(f"     Warning: Failed to write mesh: {e}")
                    except Exception as e:
                        print(f"     Warning: Failed to process mesh: {e}")
                    
                    # Create NRRD voxelization
                    try:
                        nrrd_filename = os.path.join(local_folder_path, "volume.nrrd")
                        if not os.path.exists(nrrd_filename) or os.path.getsize(nrrd_filename) < 1000:
                            # Scale neuron from nanometers to microns for voxelization
                            neuron_microns = transformed_neuron.copy()
                            neuron_microns.nodes[['x', 'y', 'z']] = neuron_microns.nodes[['x', 'y', 'z']] / 1000
                            
                            # Use appropriate bounds based on template (in microns)
                            if 'VNC' in template_name.upper():
                                # VNC template bounds (these may need adjustment)
                                bounds = [[0, 300], [0, 200], [0, 400]]
                            else:
                                # Brain template bounds (JRC2018U)
                                bounds = [[0, 627.3695649], [0, 293.1875965], [0, 173]]
                            
                            vx = navis.voxelize(neuron_microns,
                                              pitch=[0.5189161, 0.5189161, 1.0],  # pitch in microns
                                              bounds=bounds,
                                              parallel=True)
                            vx.grid = (vx.grid).astype('uint8') * 255
                            try:
                                navis.write_nrrd(vx, filepath=nrrd_filename, compression_level=9)
                                print(f"     NRRD saved: {nrrd_filename.replace('/IMAGE_WRITE/', 'http://www.virtualflybrain.org/data/')}")
                            except AttributeError:
                                print(f"     Warning: navis.write_nrrd not available, skipping NRRD for {body_id}")
                            except Exception as e:
                                print(f"     Warning: Failed to write NRRD: {e}")
                    except Exception as e:
                        print(f"     Warning: Failed to create NRRD: {e}")
            
        except Exception as e:
            print(f"Warning: Failed to process neuron {body_id}. Error: {e}")

def main():
    # Setup R environment for BANC transformations
    setup_r_environment()
    
    # Download transforms for navis
    flybrains.download_jrc_transforms()
    flybrains.download_jefferislab_transforms()
    flybrains.register_transforms()

    # Setup connection to the VFB Neo4j database
    kbw = VfbConnect(neo_endpoint='http://kb.virtualflybrain.org:80', 
                     neo_credentials=('neo4j', os.environ.get('password')))

    # Query for BANC dataset (Bates2025)
    cypher_query = '''
    MATCH (d:DataSet {short_form:'Bates2025'})<-[:has_source]-(i:Individual)<-[:depicts]-(ic:Individual)
    -[r:in_register_with]->(tc:Template)
    RETURN r.filename[0] as root_id, r.folder[0] as folder
    '''

    # Execute the Cypher query
    output = kbw.nc.commit_list(statements=[cypher_query])

    if output is False or not output:
        print("An error occurred while executing the Cypher query.")
        print("Checking for BANC dataset in the database...")
        exit(1)

    query_data_df = pd.DataFrame(output[0]['data'])['row'].apply(pd.Series)
    total_items = len(query_data_df[0])

    # Load configuration from environment variables
    max_chunk_size = int(os.environ.get('max_chunk_size', 10))
    max_workers = int(os.environ.get('max_workers', 5))

    # Warning: R operations are not thread-safe
    if R_AVAILABLE and max_workers > 1:
        print("Warning: Using rpy2 with multiple workers may cause thread safety issues.")
        print("Consider setting max_workers=1 or use subprocess mode for R.")

    # Process in chunks using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        chunk = []

        for index, result in query_data_df.iterrows():
            print(f"Processing item {index + 1} of {total_items}")
            body_id, folder_url = result[0], result[1]
            try:
                body_id = int(body_id)
            except ValueError as e:
                print(f"Warning: body_id {body_id} is not an integer. Error: {e}")
                continue

            # Add the task to the chunk
            chunk.append((body_id, folder_url))

            # If chunk size reaches max_chunk_size, process the chunk
            if len(chunk) >= max_chunk_size:
                for body_id, folder_url in chunk:
                    futures.append(executor.submit(process_banc_neuron, body_id, folder_url))
                chunk = []  # Reset the chunk after submitting

        # Process any remaining tasks in the last chunk
        if chunk:
            for body_id, folder_url in chunk:
                futures.append(executor.submit(process_banc_neuron, body_id, folder_url))

        # Collect results
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error in processing: {e}")

if __name__ == "__main__":
    main()
