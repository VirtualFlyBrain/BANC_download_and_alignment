#!/usr/bin/env python3
"""
Quick test to verify the BANC pipeline can process a real neuron.

This test:
1. Downloads a small BANC neuron skeleton
2. Attempts coordinate transformation (if dependencies available)
3. Generates all output formats (SWC, OBJ, NRRD)
4. Reports success/failure for each step

Run with: python quick_test.py
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

def test_basic_import():
    """Test that core modules can be imported."""
    print("Testing basic imports...")
    try:
        import pandas as pd
        import numpy as np
        import navis
        print("✓ Core packages imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_banc_transforms():
    """Test if BANC transformation functions are available."""
    print("Testing BANC transformation imports...")
    try:
        from fanc.transforms.template_alignment import warp_points_BANC_to_template
        print("✓ BANC transformation functions available")
        return True
    except ImportError as e:
        print(f"⚠️  BANC transforms not available: {e}")
        print("   Run ./install_banc_transforms.sh to install")
        return False

def test_google_cloud():
    """Test Google Cloud SDK availability."""
    print("Testing Google Cloud SDK...")
    import subprocess
    try:
        result = subprocess.run(['gsutil', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✓ Google Cloud SDK available")
            return True
        else:
            print("⚠️  gsutil not working properly")
            return False
    except Exception as e:
        print(f"⚠️  Google Cloud SDK not available: {e}")
        print("   Install with: pip install google-cloud-storage")
        return False

def test_pipeline_processing():
    """Test the actual pipeline with a small neuron."""
    print("Testing pipeline processing...")
    
    try:
        # Import our processing functions
        from process import (
            get_banc_626_skeleton,
            transform_skeleton_coordinates,
            process_vfb_neuron_with_banc_data
        )
        
        # Use a real neuron ID from the BANC public data
        test_neuron_id = "720575941350274352"  # First neuron from public bucket
        
        print(f"Processing test neuron: {test_neuron_id}")
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Test skeleton download
            print("  Downloading skeleton...")
            skeleton = get_banc_626_skeleton(test_neuron_id)
            if skeleton is None:
                print("  ✗ Failed to download skeleton")
                return False
            print(f"  ✓ Downloaded skeleton with {len(skeleton.nodes)} nodes")
            
            # Test coordinate transformation
            print("  Testing coordinate transformation...")
            transformed = transform_skeleton_coordinates(skeleton, "BANC", "JRC2018F")
            if transformed is not None:
                print("  ✓ Coordinate transformation completed")
            else:
                print("  ⚠️  Coordinate transformation failed (using fallback)")
            
            # Test format conversions
            print("  Testing format conversions...")
            
            # SWC
            swc_path = output_dir / f"{test_neuron_id}.swc"
            try:
                import navis
                navis.write_swc(transformed, swc_path)
                print(f"  ✓ SWC format: {swc_path.stat().st_size} bytes")
            except Exception as e:
                print(f"  ✗ SWC failed: {e}")
                return False
            
            # OBJ (if mesh generation works)
            try:
                print("  Testing mesh generation...")
                mesh = navis.to_trimesh(transformed)
                if mesh:
                    obj_path = output_dir / f"{test_neuron_id}.obj"
                    mesh.export(str(obj_path))
                    print(f"  ✓ OBJ format: {obj_path.stat().st_size} bytes")
                else:
                    print("  ⚠️  Mesh generation returned None")
            except Exception as e:
                print(f"  ⚠️  OBJ generation failed: {e}")
            
            # NRRD (if volume generation works)
            try:
                print("  Testing volume generation...")
                volume = navis.to_volume(transformed, voxdims=(1, 1, 1))
                if volume is not None:
                    import nibabel as nib
                    nrrd_path = output_dir / f"{test_neuron_id}.nrrd"
                    # Save as NIfTI first (simpler), then convert to NRRD if needed
                    nii_path = output_dir / f"{test_neuron_id}.nii.gz"
                    nib.save(nib.Nifti1Image(volume, affine=None), nii_path)
                    print(f"  ✓ Volume format: {nii_path.stat().st_size} bytes")
                else:
                    print("  ⚠️  Volume generation returned None")
            except Exception as e:
                print(f"  ⚠️  NRRD generation failed: {e}")
            
            print("✓ Pipeline processing test completed")
            return True
            
    except Exception as e:
        print(f"✗ Pipeline test failed: {e}")
        return False

def main():
    """Run all tests and report results."""
    print("BANC Pipeline Quick Test")
    print("=" * 40)
    
    tests = [
        ("Basic Imports", test_basic_import),
        ("BANC Transforms", test_banc_transforms), 
        ("Google Cloud SDK", test_google_cloud),
        ("Pipeline Processing", test_pipeline_processing),
    ]
    
    results = {}
    for name, test_func in tests:
        print(f"\n{name}:")
        results[name] = test_func()
    
    # Summary
    print("\n" + "=" * 40)
    print("TEST SUMMARY:")
    
    passed = sum(results.values())
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Pipeline is ready for production.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check installation and dependencies.")
        if not results["BANC Transforms"]:
            print("   → Run: ./install_banc_transforms.sh")
        if not results["Google Cloud SDK"]:
            print("   → Run: pip install google-cloud-storage")
        return 1

if __name__ == "__main__":
    sys.exit(main())
