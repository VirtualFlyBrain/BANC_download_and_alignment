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


def process_neuron(neuron_id, formats=['swc', 'json'], output_dir='banc_vfb_output'):
    """
    Process a single neuron through the BANC->VFB pipeline with real public data.
    
    Args:
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
