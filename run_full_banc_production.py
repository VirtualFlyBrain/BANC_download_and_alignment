#!/usr/bin/env python3
"""
Full BANC Production Pipeline

This script:
1. Queries VFB database for all BANC neurons
2. Downloads and processes each neuron from public BANC data
3. Transforms coordinates to appropriate template spaces (JRC2018U/VNC)
4. Creates properly formatted output files (SWC, OBJ, NRRD) with correct metadata
5. Places files in template-specific subdirectories
6. Resumes from failures and skips existing processed neurons
7. Handles proper coordinate units and voxel metadata

Usage:
    python run_full_banc_production.py [options]

Examples:
    python run_full_banc_production.py --limit 10 --dry-run
    python run_full_banc_production.py --output-dir /vfb/data --formats swc,obj,nrrd
    python run_full_banc_production.py --resume --skip-existing
"""

import argparse
import os
import sys
import json
import time
import logging
import re
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import our processing functions
from process import (
    get_vfb_banc_neurons,
    get_banc_626_skeleton, 
    transform_skeleton_coordinates, 
    create_vfb_file
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('banc_production.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def resolve_data_folder(base_path):
    """
    Resolve data folder path with environment-specific mappings.
    
    Handles mapping between:
    - Local development: /data/ stays as /data/
    - Jenkins production: /data/ becomes /IMAGE_WRITE/
    
    Args:
        base_path (str): Base output path
        
    Returns:
        Path: Resolved path object
    """
    # Get environment-specific data folder
    data_folder = os.getenv('DATA_FOLDER', '/data/')
    
    # Ensure trailing slash
    if not data_folder.endswith('/'):
        data_folder += '/'
    
    base_path = str(base_path)
    
    # Handle path resolution based on environment
    if base_path.startswith('/data/'):
        # Replace /data/ with the configured DATA_FOLDER
        resolved_path = base_path.replace('/data/', data_folder, 1)
    elif 'IMAGE_WRITE' in data_folder and not base_path.startswith('/IMAGE_WRITE/'):
        # If DATA_FOLDER points to IMAGE_WRITE but path doesn't include it
        if base_path.startswith('/'):
            resolved_path = data_folder.rstrip('/') + base_path
        else:
            resolved_path = data_folder + base_path
    else:
        # Use path as-is if it doesn't match patterns
        resolved_path = base_path
    
    resolved = Path(resolved_path)
    
    logger.info(f"Path resolution: {base_path} → {resolved}")
    logger.info(f"DATA_FOLDER environment: {data_folder}")
    
    return resolved


class BANCProductionProcessor:
    """Complete BANC production processing pipeline."""
    
    def __init__(self, output_dir='vfb_banc_data', formats=['swc', 'obj', 'nrrd'], 
                 skip_existing=True, max_workers=1, brain_template='JRC2018U', vnc_template='JRCVNC2018U'):
        
        # Resolve output directory with environment-specific mapping
        self.output_dir = resolve_data_folder(output_dir)
        self.formats = formats
        self.skip_existing = skip_existing
        self.max_workers = max_workers
        self.brain_template = brain_template
        self.vnc_template = vnc_template
        
        # Template directory structure using configurable template names
        self.template_dirs = {
            self.brain_template: self.output_dir / self.brain_template,
            self.vnc_template: self.output_dir / self.vnc_template
        }
        
        # Create directory structure
        self.setup_directories()
        
        # Processing state
        self.state_file = self.output_dir / 'processing_state.json'
        self.load_state()
        
    def setup_directories(self):
        """Create template-specific output directories."""
        logger.info("Setting up directory structure...")
        logger.info(f"Base output directory: {self.output_dir}")
        logger.info(f"Brain template: {self.brain_template}")
        logger.info(f"VNC template: {self.vnc_template}")
        
        # Create base output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create template subdirectories
        for template, path in self.template_dirs.items():
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path}")
    
    def load_state(self):
        """Load processing state from previous runs."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.info(f"Loaded state: {len(self.state.get('processed', []))} previously processed")
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")
                self.state = {'processed': [], 'failed': [], 'last_run': None}
        else:
            self.state = {'processed': [], 'failed': [], 'last_run': None}
    
    def save_state(self):
        """Save current processing state."""
        self.state['last_run'] = datetime.now().isoformat()
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state: {e}")
    
    def get_template_space(self, skeleton):
        """Determine appropriate template space based on neuron coordinates."""
        try:
            coords = skeleton.nodes[['x', 'y', 'z']].values
            avg_y = np.mean(coords[:, 1])
            
            # BANC coordinate analysis: y > ~320,000 nm is VNC region
            if avg_y > 320000:
                return self.vnc_template
            else:
                return self.brain_template
        except Exception as e:
            logger.warning(f"Could not determine template space: {e}, defaulting to {self.brain_template}")
            return self.brain_template
    
    def get_output_paths(self, neuron_id, template_space):
        """Generate output file paths for a neuron."""
        template_dir = self.template_dirs[template_space]
        
        # Create neuron-specific subdirectory using VFB short_form format
        neuron_dir = template_dir / f"BANC_{neuron_id}"
        neuron_dir.mkdir(exist_ok=True)
        
        paths = {}
        for fmt in self.formats:
            paths[fmt] = neuron_dir / f"BANC_{neuron_id}.{fmt}"
        
        return paths
    
    def files_exist(self, paths):
        """Check if all required output files already exist."""
        if not self.skip_existing:
            return False
        
        return all(path.exists() and path.stat().st_size > 0 for path in paths.values())
    
    def create_nrrd_with_metadata(self, skeleton, output_path, template_space):
        """Create NRRD file with proper voxel metadata."""
        try:
            import nrrd
            
            coords = skeleton.nodes[['x', 'y', 'z']].values
            
            # Determine voxel size based on template space
            if template_space == self.brain_template:
                # JRC2018U standard voxel size: 0.622 x 0.622 x 0.622 µm
                voxel_size = [0.622, 0.622, 0.622]
                space = 'left-posterior-superior'
            else:  # VNC template
                # JRCVNC2018U standard voxel size: 0.4 x 0.4 x 0.4 µm  
                voxel_size = [0.4, 0.4, 0.4]
                space = 'left-posterior-superior'
            
            # Create volume from skeleton coordinates
            min_coords = coords.min(axis=0)
            max_coords = coords.max(axis=0)
            
            # Convert to voxel coordinates
            min_voxel = (min_coords / voxel_size).astype(int)
            max_voxel = (max_coords / voxel_size).astype(int)
            shape = max_voxel - min_voxel + 1
            
            # Create binary volume
            volume = np.zeros(shape, dtype=np.uint8)
            
            # Mark skeleton points
            for coord in coords:
                voxel_coord = ((coord - min_coords) / voxel_size).astype(int)
                if all(0 <= voxel_coord[i] < shape[i] for i in range(3)):
                    volume[tuple(voxel_coord)] = 255
            
            # NRRD header with proper metadata
            header = {
                'space': space,
                'space directions': np.diag(voxel_size),
                'space origin': min_coords,
                'units': ['µm', 'µm', 'µm'],
                'labels': ['x', 'y', 'z'],
                'encoding': 'gzip'
            }
            
            # Save NRRD with metadata
            nrrd.write(str(output_path), volume, header)
            logger.info(f"Created NRRD with voxel size {voxel_size} µm")
            return True
            
        except ImportError:
            logger.error("NRRD format requires 'pynrrd' package: pip install pynrrd")
            return False
        except Exception as e:
            logger.error(f"NRRD creation failed: {e}")
            return False
    
    def process_single_neuron(self, neuron_info):
        """Process a single BANC neuron through the complete pipeline."""
        neuron_id = neuron_info.get('id', '').replace('BANC_', '').replace('VFB_', '')
        if not neuron_id:
            logger.error(f"Invalid neuron ID: {neuron_info}")
            return {'success': False, 'error': 'Invalid neuron ID'}
        
        logger.info(f"🧠 Processing BANC neuron: {neuron_id}")
        
        try:
            # Step 1: Download skeleton from public BANC data
            logger.info(f"  📥 Downloading skeleton...")
            skeleton = get_banc_626_skeleton(neuron_id)
            if skeleton is None:
                error = f"Failed to download skeleton for {neuron_id}"
                logger.error(f"  ❌ {error}")
                return {'success': False, 'error': error}
            
            logger.info(f"  ✅ Downloaded: {len(skeleton.nodes)} nodes")
            
            # Step 2: Determine template space
            template_space = self.get_template_space(skeleton)
            logger.info(f"  🎯 Template space: {template_space}")
            
            # Step 3: Check if files already exist
            output_paths = self.get_output_paths(neuron_id, template_space)
            if self.files_exist(output_paths):
                logger.info(f"  ⏭️  Files already exist, skipping")
                return {'success': True, 'skipped': True, 'files': output_paths}
            
            # Step 4: Transform coordinates
            logger.info(f"  🔄 Transforming coordinates...")
            if template_space == self.vnc_template:
                # BANC VNC → JRCVNC2018F → JRCVNC2018U
                transformed = transform_skeleton_coordinates(skeleton, 'BANC', 'VFB')
            else:
                # BANC Brain → JRC2018F → JRC2018U  
                transformed = transform_skeleton_coordinates(skeleton, 'BANC', 'VFB')
            
            logger.info(f"  ✅ Coordinates transformed")
            
            # Step 5: Create output files
            logger.info(f"  📁 Creating output files...")
            created_files = {}
            
            for fmt in self.formats:
                output_path = output_paths[fmt]
                
                if fmt == 'swc':
                    # SWC format with proper units (micrometers)
                    import navis
                    navis.write_swc(transformed, str(output_path))
                    created_files[fmt] = str(output_path)
                    logger.info(f"    ✅ SWC: {output_path.name}")
                    
                elif fmt == 'obj':
                    # OBJ 3D mesh format
                    try:
                        mesh = navis.mesh_neuron(transformed)
                        with open(output_path, 'w') as f:
                            # Simple OBJ format
                            vertices = mesh.vertices
                            faces = mesh.faces
                            
                            for v in vertices:
                                f.write(f"v {v[0]} {v[1]} {v[2]}\n")
                            for face in faces:
                                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
                        
                        created_files[fmt] = str(output_path)
                        logger.info(f"    ✅ OBJ: {output_path.name}")
                    except Exception as e:
                        logger.warning(f"    ⚠️  OBJ creation failed: {e}")
                
                elif fmt == 'nrrd':
                    # NRRD volume with proper metadata
                    if self.create_nrrd_with_metadata(transformed, output_path, template_space):
                        created_files[fmt] = str(output_path)
                        logger.info(f"    ✅ NRRD: {output_path.name}")
                    else:
                        logger.warning(f"    ⚠️  NRRD creation failed")
            
            # Step 6: Create metadata JSON
            json_path = output_paths['swc'].parent / f"BANC_{neuron_id}.json"
            metadata = {
                'neuron_id': neuron_id,
                'source': 'BANC',
                'template_space': template_space,
                'processing_date': datetime.now().isoformat(),
                'coordinate_units': 'micrometers',
                'voxel_size': [0.622, 0.622, 0.622] if template_space == self.brain_template else [0.4, 0.4, 0.4],
                'files': created_files,
                'node_count': len(transformed.nodes),
                'cable_length': float(transformed.cable_length) if hasattr(transformed, 'cable_length') else None
            }
            
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"  📋 Metadata: {json_path.name}")
            logger.info(f"  🎉 Successfully processed {neuron_id}")
            
            return {
                'success': True,
                'neuron_id': neuron_id,
                'template_space': template_space,
                'files': created_files,
                'metadata': str(json_path)
            }
            
        except Exception as e:
            error = f"Processing failed for {neuron_id}: {str(e)}"
            logger.error(f"  ❌ {error}")
            return {'success': False, 'error': error, 'neuron_id': neuron_id}
    
    def run_production_pipeline(self, limit=None, dry_run=False):
        """Run the complete production pipeline."""
        logger.info("🚀 Starting BANC Production Pipeline")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Formats: {', '.join(self.formats)}")
        logger.info(f"Skip existing: {self.skip_existing}")
        
        # Get all BANC neurons from VFB database
        logger.info("📋 Querying VFB database for BANC neurons...")
        try:
            all_neurons = get_vfb_banc_neurons(limit)
            logger.info(f"Found {len(all_neurons)} BANC neurons")
        except Exception as e:
            logger.error(f"Failed to query VFB database: {e}")
            return False
        
        if dry_run:
            logger.info("🔍 DRY RUN - Would process these neurons:")
            for neuron in all_neurons[:10]:  # Show first 10
                logger.info(f"  - {neuron.get('id', 'Unknown')}: {neuron.get('name', 'Unknown')}")
            if len(all_neurons) > 10:
                logger.info(f"  ... and {len(all_neurons) - 10} more")
            return True
        
        # Filter out already processed neurons
        if self.skip_existing:
            processed_ids = set(self.state.get('processed', []))
            neurons_to_process = [n for n in all_neurons 
                                if n.get('id', '').replace('BANC_', '').replace('VFB_', '') not in processed_ids]
            logger.info(f"Skipping {len(all_neurons) - len(neurons_to_process)} already processed neurons")
        else:
            neurons_to_process = all_neurons
        
        if not neurons_to_process:
            logger.info("✅ All neurons already processed!")
            return True
        
        logger.info(f"Processing {len(neurons_to_process)} neurons...")
        
        # Process neurons
        successful = 0
        failed = 0
        skipped = 0
        
        try:
            if self.max_workers == 1:
                # Sequential processing
                for i, neuron in enumerate(neurons_to_process, 1):
                    logger.info(f"\n[{i}/{len(neurons_to_process)}] Processing neuron...")
                    
                    result = self.process_single_neuron(neuron)
                    
                    if result['success']:
                        if result.get('skipped'):
                            skipped += 1
                        else:
                            successful += 1
                            neuron_id = result.get('neuron_id', neuron.get('id', ''))
                            self.state['processed'].append(neuron_id)
                    else:
                        failed += 1
                        neuron_id = result.get('neuron_id', neuron.get('id', ''))
                        self.state['failed'].append({
                            'neuron_id': neuron_id,
                            'error': result.get('error', 'Unknown error'),
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    # Save state periodically
                    if (successful + failed + skipped) % 10 == 0:
                        self.save_state()
                        logger.info(f"💾 State saved - Progress: {successful}✅ {failed}❌ {skipped}⏭️")
            
            else:
                # Parallel processing
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_neuron = {
                        executor.submit(self.process_single_neuron, neuron): neuron 
                        for neuron in neurons_to_process
                    }
                    
                    for future in as_completed(future_to_neuron):
                        neuron = future_to_neuron[future]
                        try:
                            result = future.result()
                            
                            if result['success']:
                                if result.get('skipped'):
                                    skipped += 1
                                else:
                                    successful += 1
                                    neuron_id = result.get('neuron_id', neuron.get('id', ''))
                                    self.state['processed'].append(neuron_id)
                            else:
                                failed += 1
                                neuron_id = result.get('neuron_id', neuron.get('id', ''))
                                self.state['failed'].append({
                                    'neuron_id': neuron_id,
                                    'error': result.get('error', 'Unknown error'),
                                    'timestamp': datetime.now().isoformat()
                                })
                        
                        except Exception as e:
                            failed += 1
                            logger.error(f"Executor error: {e}")
                        
                        # Progress update
                        total_processed = successful + failed + skipped
                        if total_processed % 10 == 0:
                            logger.info(f"Progress: {total_processed}/{len(neurons_to_process)} "
                                      f"({successful}✅ {failed}❌ {skipped}⏭️)")
        
        except KeyboardInterrupt:
            logger.info("\n⚠️  Processing interrupted by user")
        
        finally:
            # Final state save
            self.save_state()
        
        # Summary
        logger.info("\n📊 PRODUCTION PIPELINE SUMMARY")
        logger.info("=" * 50)
        logger.info(f"✅ Successful: {successful}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"⏭️  Skipped: {skipped}")
        logger.info(f"📁 Output directory: {self.output_dir}")
        
        if failed > 0:
            logger.info("\n❌ Failed neurons:")
            for failure in self.state['failed'][-failed:]:  # Show recent failures
                logger.info(f"  - {failure['neuron_id']}: {failure['error']}")
        
        return failed == 0


def main():
    """Main entry point for the production pipeline."""
    parser = argparse.ArgumentParser(
        description="BANC Production Pipeline - Process all BANC neurons for VFB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  DATA_FOLDER    Base data folder path (default: /data/)
                 Jenkins: set to /IMAGE_WRITE/
                 Local: use default or set to repo subfolder

Examples:
  # Local development
  python run_full_banc_production.py --limit 10 --dry-run
  
  # Local with custom data folder
  export DATA_FOLDER=/Users/user/project/data/
  python run_full_banc_production.py --output-dir /data/vfb
  
  # Jenkins production
  export DATA_FOLDER=/IMAGE_WRITE/
  python run_full_banc_production.py --output-dir /data/vfb --formats swc,obj,nrrd
        """
    )
    
    parser.add_argument('--output-dir', default='vfb_banc_data',
                       help='Output directory for processed files (default: vfb_banc_data)')
    
    parser.add_argument('--formats', default='swc,obj,nrrd',
                       help='Output formats (comma-separated: swc,obj,nrrd) (default: swc,obj,nrrd)')
    
    parser.add_argument('--limit', type=int,
                       help='Limit number of neurons to process (for testing)')
    
    parser.add_argument('--max-workers', type=int, default=1,
                       help='Maximum parallel workers (default: 1)')
    
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without doing it')
    
    parser.add_argument('--no-skip-existing', action='store_true',
                       help='Reprocess existing files (default: skip existing)')
    
    parser.add_argument('--resume', action='store_true',
                       help='Resume from previous run (default behavior)')
    
    parser.add_argument('--brain-template', default='JRC2018U',
                       help='Brain template folder name (default: JRC2018U)')
    
    parser.add_argument('--vnc-template', default='JRCVNC2018U',
                       help='VNC template folder name (default: JRCVNC2018U)')
    
    args = parser.parse_args()
    
    # Show environment configuration
    data_folder = os.getenv('DATA_FOLDER', '/data/')
    logger.info(f"Environment DATA_FOLDER: {data_folder}")
    logger.info(f"Output directory argument: {args.output_dir}")
    logger.info(f"Brain template: {args.brain_template}")
    logger.info(f"VNC template: {args.vnc_template}")
    
    # Parse formats
    formats = [f.strip() for f in args.formats.split(',')]
    valid_formats = {'swc', 'obj', 'nrrd'}
    invalid_formats = set(formats) - valid_formats
    if invalid_formats:
        print(f"Error: Invalid formats: {invalid_formats}")
        print(f"Valid formats: {valid_formats}")
        return 1
    
    # Initialize processor
    processor = BANCProductionProcessor(
        output_dir=args.output_dir,
        formats=formats,
        skip_existing=not args.no_skip_existing,
        max_workers=args.max_workers,
        brain_template=args.brain_template,
        vnc_template=args.vnc_template
    )
    
    # Run pipeline
    try:
        success = processor.run_production_pipeline(
            limit=args.limit,
            dry_run=args.dry_run
        )
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
