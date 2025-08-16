#!/usr/bin/env python3
"""
BANC to VFB Processing Pipeline

This script demonstrates the complete pipeline for processing BANC connectome data
and generating VFB-compatible files.

Usage:
    python run_banc_pipeline.py [--limit N] [--output-dir DIR]

The pipeline includes:
1. VFB database queries to find BANC neurons
2. BANC skeleton generation (using pcg_skel or fallback methods)
3. Coordinate transformation from BANC to VFB space
4. Creation of VFB-compatible files (SWC and JSON formats)

Author: AI Assistant
Date: August 2025
"""

import argparse
import os
import sys
from datetime import datetime
from process import (
    get_vfb_banc_neurons, 
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


def process_neuron(neuron, output_dir, verbose=True):
    """
    Process a single BANC neuron through the complete pipeline.
    
    Args:
        neuron: Dictionary with neuron information (id, name, status)
        output_dir: Directory to save output files
        verbose: Whether to print detailed progress
    
    Returns:
        Dictionary with processing results
    """
    neuron_id = neuron['id']
    result = {
        'neuron_id': neuron_id,
        'name': neuron['name'],
        'success': False,
        'skeleton_generated': False,
        'coordinates_transformed': False,
        'files_created': [],
        'errors': []
    }
    
    try:
        if verbose:
            print(f"\n{'='*50}")
            print(f"Processing neuron: {neuron_id}")
            print(f"Name: {neuron['name']}")
            print(f"Status: {neuron['status']}")
            print(f"{'='*50}")
        
        # Step 1: Generate skeleton
        if verbose:
            print("\n1. Generating skeleton...")
        
        skeleton = get_banc_626_skeleton(neuron_id)
        
        if skeleton is None:
            result['errors'].append("Failed to generate skeleton")
            return result
        
        result['skeleton_generated'] = True
        if verbose:
            print(f"   ✓ Skeleton generated with {len(skeleton.nodes)} nodes")
        
        # Step 2: Transform coordinates  
        if verbose:
            print("\n2. Transforming coordinates...")
        
        transformed = transform_skeleton_coordinates(skeleton)
        
        if transformed is None:
            result['errors'].append("Failed to transform coordinates")
            return result
        
        result['coordinates_transformed'] = True
        if verbose:
            print("   ✓ Coordinates transformed to VFB space")
        
        # Step 3: Create output files
        if verbose:
            print("\n3. Creating output files...")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare metadata
        metadata = {
            'source': 'BANC_626',
            'vfb_id': neuron_id,
            'name': neuron['name'],
            'status': neuron['status'],
            'processing_date': datetime.now().isoformat(),
            'pipeline_version': '1.0',
            'method': 'pcg_skel_with_fallback'
        }
        
        # Create SWC file
        swc_path = os.path.join(output_dir, f"{neuron_id}.swc")
        swc_success = create_vfb_file(transformed, swc_path, neuron_id, metadata)
        
        if swc_success:
            result['files_created'].append(swc_path)
            if verbose:
                print(f"   ✓ SWC file created: {swc_path}")
        
        # Create JSON file
        json_path = os.path.join(output_dir, f"{neuron_id}.json")
        json_success = create_vfb_file(transformed, json_path, neuron_id, metadata)
        
        if json_success:
            result['files_created'].append(json_path)
            if verbose:
                print(f"   ✓ JSON file created: {json_path}")
        
        if swc_success and json_success:
            result['success'] = True
            if verbose:
                print("\n   ✓ Processing completed successfully!")
        else:
            result['errors'].append("File creation partially failed")
            
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        result['errors'].append(error_msg)
        if verbose:
            print(f"\n   ✗ Error: {error_msg}")
    
    return result


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(
        description="BANC to VFB Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_banc_pipeline.py --limit 5
    python run_banc_pipeline.py --output-dir /path/to/output --limit 10
    python run_banc_pipeline.py --no-verbose
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
        '--no-verbose', 
        action='store_true',
        help='Suppress detailed output'
    )
    
    args = parser.parse_args()
    verbose = not args.no_verbose
    
    if verbose:
        print("BANC to VFB Processing Pipeline")
        print("="*50)
        print(f"Limit: {args.limit} neurons")
        print(f"Output directory: {args.output_dir}")
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
        
        result = process_neuron(neuron, args.output_dir, verbose)
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
