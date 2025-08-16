#!/usr/bin/env python3
"""
BANC to VFB Processing Pipeline

This script processes specific BANC neuron IDs and generates VFB-compatible files.

Usage:
    python run_banc_pipeline.py NEURON_ID [NEURON_ID ...] [--formats FORMAT] [--output-dir DIR]
    
Examples:
    python run_banc_pipeline.py 720575941350274352
    python run_banc_pipeline.py 720575941350274352 --formats swc,obj,nrrd
    python run_banc_pipeline.py 720575941350274352 720575941350334256 --formats swc

The pipeline includes:
1. Download BANC skeleton from public bucket
2. Coordinate transformation from BANC to VFB space (JRC2018F/VNC)
3. Multi-format output (SWC, OBJ mesh, NRRD volume)

Author: AI Assistant
Date: December 2024
"""

import argparse
import os
import sys
from datetime import datetime
from process import (
    get_banc_626_skeleton, 
    transform_skeleton_coordinates, 
    create_vfb_file
)


def setup_environment():
    """Set up environment variables for BANC processing."""
    # Set authentication token if provided
    if 'FLYWIRE_SECRET' not in os.environ:
        # Use the provided token
        os.environ['FLYWIRE_SECRET'] = '4f286f518add5e15c2c82c20299295c7'
    
    # Set processing parameters
    os.environ['password'] = 'banana2-funky-Earthy-Irvin-Tactful0-felice9'
    os.environ['max_chunk_size'] = '3'
    os.environ['max_workers'] = '1'


def process_neuron(neuron_id, formats=['swc'], output_dir='banc_vfb_output'):
    """
    Process a single neuron through the BANC->VFB pipeline with real public data.
    
    Args:
        neuron_id: BANC segment ID to process
        formats: List of output formats ['swc', 'obj', 'nrrd']
        output_dir: Directory for output files
        
    Returns:
        Dict with processing results and file paths
    """
    print(f"\n🧠 Processing BANC neuron: {neuron_id}")
    
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Step 1: Download skeleton from BANC public data
        print("📥 Downloading skeleton from BANC public bucket...")
        skeleton = get_banc_626_skeleton(neuron_id)
        
        if skeleton is None:
            print(f"❌ Failed to download skeleton for {neuron_id}")
            return {"success": False, "error": "Skeleton download failed"}
        
        print(f"✅ Downloaded skeleton: {len(skeleton.nodes)} nodes")
        
        # Step 2: Transform coordinates to VFB space
        print("🔄 Transforming coordinates BANC → JRC2018F/VNC...")
        transformed_skeleton = transform_skeleton_coordinates(
            skeleton, 
            source_space="BANC", 
            target_space="VFB"
        )
        
        if transformed_skeleton is None:
            print("❌ Coordinate transformation failed")
            return {"success": False, "error": "Coordinate transformation failed"}
        
        print("✅ Coordinate transformation completed")
        
        # Step 3: Generate outputs in requested formats
        results = {"success": True, "files": {}}
        
        for format_type in formats:
            print(f"📄 Generating {format_type.upper()} format...")
            
            try:
                if format_type.lower() == 'swc':
                    # SWC skeleton format
                    swc_path = os.path.join(output_dir, f"{neuron_id}.swc")
                    import navis
                    navis.write_swc(transformed_skeleton, swc_path)
                    results['files']['swc'] = swc_path
                    print(f"   ✅ SWC: {swc_path}")
                
                elif format_type.lower() == 'obj':
                    # OBJ mesh format
                    obj_path = os.path.join(output_dir, f"{neuron_id}.obj")
                    try:
                        import navis
                        mesh = navis.to_trimesh(transformed_skeleton)
                        if mesh:
                            mesh.export(obj_path)
                            results['files']['obj'] = obj_path
                            print(f"   ✅ OBJ: {obj_path}")
                        else:
                            print(f"   ⚠️  OBJ: Mesh generation returned None")
                    except Exception as e:
                        print(f"   ⚠️  OBJ generation failed: {e}")
                
                elif format_type.lower() == 'nrrd':
                    # NRRD volume format
                    nrrd_path = os.path.join(output_dir, f"{neuron_id}.nrrd")
                    try:
                        import navis
                        # Generate volume representation
                        volume = navis.to_volume(transformed_skeleton, voxdims=(1, 1, 1))
                        if volume is not None:
                            # Save as NRRD using SimpleITK or similar
                            import nibabel as nib
                            nii_path = os.path.join(output_dir, f"{neuron_id}.nii.gz")
                            nib.save(nib.Nifti1Image(volume, affine=None), nii_path)
                            results['files']['nrrd'] = nii_path  # Using NIfTI for now
                            print(f"   ✅ Volume: {nii_path}")
                        else:
                            print(f"   ⚠️  Volume generation returned None")
                    except Exception as e:
                        print(f"   ⚠️  NRRD generation failed: {e}")
                
                else:
                    print(f"   ⚠️  Unknown format: {format_type}")
            
            except Exception as e:
                print(f"   ❌ {format_type.upper()} generation failed: {e}")
        
        # Step 4: Create VFB metadata JSON
        try:
            json_path = os.path.join(output_dir, f"{neuron_id}.json")
            vfb_data = create_vfb_file(
                transformed_skeleton, 
                neuron_id, 
                json_path
            )
            results['files']['json'] = json_path
            print(f"📋 VFB metadata: {json_path}")
        except Exception as e:
            print(f"⚠️  VFB metadata generation failed: {e}")
        
        print(f"🎉 Successfully processed {neuron_id}")
        return results
        
    except Exception as e:
        print(f"❌ Error processing neuron {neuron_id}: {e}")
        return {"success": False, "error": str(e)}
        neuron_id: Either VFB ID or BANC segment ID 
        formats: List of output formats to generate
        output_dir: Output directory for processed files
    
    Returns:
        dict: Processing results
    """
    try:
        from process import process_vfb_neuron_with_banc_data, list_available_banc_neurons
        
        # Check if this looks like a BANC segment ID (all digits)
        if neuron_id.isdigit():
            print(f"Processing BANC segment ID: {neuron_id}")
            
            # For BANC IDs, create a VFB test ID and use the BANC ID directly
            vfb_id = f"VFB_BANC_{neuron_id}"
            banc_id = neuron_id
            
        else:
            print(f"Processing VFB neuron ID: {neuron_id}")
            vfb_id = neuron_id
            banc_id = None  # Will need to be provided or mapped
        
        # Process with the new comprehensive function
        results = process_vfb_neuron_with_banc_data(
            vfb_neuron_id=vfb_id,
            banc_segment_id=banc_id,
            output_dir=output_dir,
            formats=formats
        )
        
        return results
        
    except ImportError as e:
        print(f"Import error: {e}")
        return {'success': False, 'error': 'Failed to import processing functions'}
    except Exception as e:
        print(f"Error processing neuron {neuron_id}: {e}")
        return {'success': False, 'error': str(e)}


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(
        description="BANC to VFB Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_banc_pipeline.py --limit 5
    python run_banc_pipeline.py --output-dir /path/to/output --limit 10
    python run_banc_pipeline.py --formats swc,json,obj,nrrd --limit 3
    python run_banc_pipeline.py --formats obj,nrrd --no-verbose
        """
    )
    
    parser.add_argument(
        '--limit', 
        type=int, 
        default=5, 
        help='Maximum number of neurons to process (default: 5)'
    )
    
    parser.add_argument(
        '--output-dir', 
        type=str, 
        default='banc_vfb_output',
        help='Output directory for processed files (default: banc_vfb_output)'
    )
    
    parser.add_argument(
        '--formats',
        type=str,
        default='swc,json',
        help='Output formats (comma-separated): swc,json,obj,nrrd (default: swc,json)'
    )
    
    parser.add_argument(
        '--no-verbose', 
        action='store_true',
        help='Suppress detailed output'
    )
    
    args = parser.parse_args()
    verbose = not args.no_verbose
    
    # Parse formats
    formats = [fmt.strip() for fmt in args.formats.split(',')]
    valid_formats = ['swc', 'json', 'obj', 'nrrd']
    invalid_formats = [fmt for fmt in formats if fmt not in valid_formats]
    
    if invalid_formats:
        print(f"Error: Invalid format(s): {', '.join(invalid_formats)}")
        print(f"Valid formats are: {', '.join(valid_formats)}")
        sys.exit(1)
    
    if verbose:
        print("BANC to VFB Processing Pipeline")
        print("="*50)
        print(f"Limit: {args.limit} neurons")
        print(f"Output directory: {args.output_dir}")
        print(f"Output formats: {', '.join(formats)}")
        print("="*50)
    
    # Set up environment
    setup_environment()
    
    # Query VFB database for BANC neurons
    if verbose:
        print("\nQuerying VFB database for BANC neurons...")
    
    neurons = get_vfb_banc_neurons(limit=args.limit)
    
    if not neurons:
        print("No neurons found in VFB database. Exiting.")
        sys.exit(1)
    
    if verbose:
        print(f"Found {len(neurons)} neurons to process")
    
    # Process each neuron
    results = []
    successful = 0
    
    for i, neuron in enumerate(neurons, 1):
        if verbose:
            print(f"\n[{i}/{len(neurons)}] Processing {neuron['id']}...")
        
        result = process_neuron(neuron, args.output_dir, formats, verbose)
        results.append(result)
        
        if result['success']:
            successful += 1
    
    # Print summary
    print(f"\n{'='*50}")
    print("PROCESSING SUMMARY")
    print(f"{'='*50}")
    print(f"Total neurons processed: {len(neurons)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(neurons) - successful}")
    
    if args.output_dir and os.path.exists(args.output_dir):
        file_count = len([f for f in os.listdir(args.output_dir) if f.endswith(('.swc', '.json'))])
        print(f"Output files created: {file_count}")
        print(f"Output directory: {args.output_dir}")
    
    # Show errors if any
    errors = []
    for result in results:
        if result['errors']:
            errors.extend([f"{result['neuron_id']}: {err}" for err in result['errors']])
    
    if errors:
        print(f"\nErrors encountered:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more errors")
    
    print(f"\nPipeline completed at {datetime.now()}")


if __name__ == "__main__":
    main()
