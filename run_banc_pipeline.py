#!/usr/bin/env python3
"""
BANC to VFB Processing Pipeline

Production-ready script for processing BANC neuron data from public bucket.

Usage:
    python run_banc_pipeline.py NEURON_ID [NEURON_ID ...] [--formats swc,obj,nrrd]

Examples:
    python run_banc_pipeline.py 720575941350274352
    python run_banc_pipeline.py 720575941350274352 --formats swc,obj,nrrd
    python run_banc_pipeline.py 720575941350274352 720575941350334256 --formats swc
"""

import argparse
import os
import sys
import numpy as np
from process import (
    get_banc_626_skeleton, 
    transform_skeleton_coordinates, 
    create_vfb_file
)


def process_neuron(neuron_id, formats=['swc'], output_dir='banc_vfb_output'):
    """Process a single BANC neuron through the complete pipeline."""
    print(f"\n🧠 Processing BANC neuron: {neuron_id}")
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        # Download skeleton from BANC public data
        print("📥 Downloading skeleton...")
        skeleton = get_banc_626_skeleton(neuron_id)
        if skeleton is None:
            return {"success": False, "error": "Download failed"}
        
        print(f"✅ Downloaded: {len(skeleton.nodes)} nodes")
        
        # Transform coordinates
        print("🔄 Transforming coordinates...")
        transformed = transform_skeleton_coordinates(skeleton, "BANC", "VFB")
        if transformed is None:
            return {"success": False, "error": "Transform failed"}
        
        print("✅ Coordinates transformed")
        
        # Generate output formats
        results = {"success": True, "files": {}}
        
        for fmt in formats:
            print(f"📄 Generating {fmt.upper()}...")
            
            if fmt == 'swc':
                import navis
                path = os.path.join(output_dir, f"{neuron_id}.swc")
                navis.write_swc(transformed, path)
                results['files']['swc'] = path
                print(f"   ✅ {path}")
            
            elif fmt == 'obj':
                try:
                    import navis
                    mesh = navis.to_trimesh(transformed)
                    if mesh:
                        path = os.path.join(output_dir, f"{neuron_id}.obj")
                        mesh.export(path)
                        results['files']['obj'] = path
                        print(f"   ✅ {path}")
                    else:
                        print("   ⚠️  Mesh generation failed")
                except Exception as e:
                    print(f"   ⚠️  OBJ error: {e}")
            
            elif fmt == 'nrrd':
                # NRRD volume format (requires additional processing)
                try:
                    import nrrd
                    path = os.path.join(output_dir, f"{neuron_id}.nrrd")
                    
                    # Create simple volume representation from skeleton
                    # Note: This is a basic implementation - full volume reconstruction would require mesh data
                    coords = transformed.nodes[['x', 'y', 'z']].values
                    
                    # Create a simple binary volume around skeleton points
                    min_coords = coords.min(axis=0).astype(int)
                    max_coords = coords.max(axis=0).astype(int)
                    shape = (max_coords - min_coords + 1).astype(int)
                    
                    volume = np.zeros(shape, dtype=np.uint8)
                    
                    # Mark skeleton points in volume
                    for coord in coords:
                        idx = (coord - min_coords).astype(int)
                        if all(0 <= idx[i] < shape[i] for i in range(3)):
                            volume[tuple(idx)] = 255
                    
                    # Save as NRRD
                    nrrd.write(path, volume)
                    results['files']['nrrd'] = path
                    print(f"   ✅ {path}")
                    
                except ImportError:
                    print("   ⚠️  NRRD requires 'pynrrd' package: pip install pynrrd")
                except Exception as e:
                    print(f"   ⚠️  NRRD error: {e}")
        
        # Create VFB metadata
        try:
            json_path = os.path.join(output_dir, f"{neuron_id}.json")
            create_vfb_file(transformed, neuron_id, json_path)
            results['files']['json'] = json_path
            print(f"📋 Metadata: {json_path}")
        except Exception as e:
            print(f"⚠️  Metadata error: {e}")
        
        print(f"🎉 Success: {neuron_id}")
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description="BANC to VFB Processing Pipeline")
    parser.add_argument('neuron_ids', nargs='+', help='BANC segment IDs')
    parser.add_argument('--formats', default='swc', help='Output formats: swc,obj,nrrd')
    parser.add_argument('--output-dir', default='banc_vfb_output', help='Output directory')
    
    args = parser.parse_args()
    
    # Parse and validate formats
    formats = [f.strip().lower() for f in args.formats.split(',')]
    valid_formats = ['swc', 'obj', 'nrrd']
    invalid = [f for f in formats if f not in valid_formats]
    
    if invalid:
        print(f"❌ Invalid formats: {invalid}")
        print(f"Valid formats: {valid_formats}")
        return 1
    
    print("🚀 BANC → VFB Processing Pipeline")
    print(f"Neurons: {args.neuron_ids}")
    print(f"Formats: {formats}")
    print(f"Output: {args.output_dir}")
    
    # Process each neuron
    results = {}
    successful = 0
    
    for neuron_id in args.neuron_ids:
        result = process_neuron(neuron_id, formats, args.output_dir)
        results[neuron_id] = result
        if result.get('success', False):
            successful += 1
    
    # Summary
    total = len(args.neuron_ids)
    failed = total - successful
    
    print(f"\n📊 SUMMARY: {successful}/{total} successful")
    
    if successful > 0:
        print(f"✅ Output directory: {args.output_dir}")
    
    if failed > 0:
        print(f"❌ Failed neurons:")
        for nid, result in results.items():
            if not result.get('success'):
                print(f"   {nid}: {result.get('error', 'Unknown')}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
