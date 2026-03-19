"""
Data Curation Pipeline: Create Balanced 5-Category Unified Datasets
Senior CV Engineer Solution
"""

import pandas as pd
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    BASE_PATH = Path(r'c:\DD\TTS_SDS\TEST2\data')
    CSV_PATH = BASE_PATH / 'annotations' / 'csv'
    
    # 5 Categories to ensure
    CATEGORIES = {
        'Serve': ['serev'],
        'Forehand Chop': ['forehand_chop'],
        'Backhand Chop': ['backhand_chop'],
        'Forehand Smash': ['forehand_smash'],
        'Backhand Smash': ['backhand_smash']
    }
    
    # Video groupings
    VIDEO_TYPES = {
        'match_rallies': list(range(1, 7)),      # Videos 1-6
        'training_drills': list(range(7, 15))    # Videos 7-14
    }
    
    OUTPUT_BASE = BASE_PATH / 'unified_balanced_datasets'


# ============================================================================
# PHASE 1: ANALYSIS
# ============================================================================

class AnalysisPhase:
    """Analyze which categories are present in each video"""
    
    def __init__(self):
        self.video_analysis = {}
        self.category_distribution = {}
    
    def load_and_analyze(self):
        """Load all videos and analyze category presence"""
        logger.info("=" * 70)
        logger.info("PHASE 1: ANALYSIS - Category Coverage per Video")
        logger.info("=" * 70)
        
        for video_num in range(1, 15):
            csv_file = Config.CSV_PATH / f'TTVideo_{video_num}.csv'
            
            if csv_file.exists():
                df = pd.read_csv(csv_file)
                categories_present = set()
                category_counts = defaultdict(int)
                
                # Classify strokes
                for stroke_type in df['stroke_type']:
                    for category, stroke_list in Config.CATEGORIES.items():
                        if stroke_type in stroke_list:
                            categories_present.add(category)
                            category_counts[category] += 1
                            break
                
                # Store analysis
                video_type = 'Match' if video_num <= 6 else 'Training'
                self.video_analysis[video_num] = {
                    'video_type': video_type,
                    'categories_present': sorted(list(categories_present)),
                    'category_counts': dict(category_counts),
                    'total_strokes': len(df),
                    'has_all_5': len(categories_present) == 5
                }
            else:
                logger.warning(f"File not found: {csv_file}")
        
        self._print_analysis()
        return self.video_analysis
    
    def _print_analysis(self):
        """Print analysis results"""
        logger.info("\nVIDEO ANALYSIS RESULTS:")
        logger.info("-" * 70)
        
        complete_videos = []
        incomplete_videos = []
        
        for video_num in sorted(self.video_analysis.keys()):
            info = self.video_analysis[video_num]
            status = "✓ COMPLETE" if info['has_all_5'] else "✗ INCOMPLETE"
            categories = info['categories_present']
            
            logger.info(f"Video {video_num:2d} ({info['video_type']:8}): {status}")
            logger.info(f"  Categories: {categories}")
            logger.info(f"  Counts: {info['category_counts']}")
            
            if info['has_all_5']:
                complete_videos.append(video_num)
            else:
                incomplete_videos.append(video_num)
        
        logger.info("-" * 70)
        logger.info(f"Videos with ALL 5 categories: {len(complete_videos)}")
        logger.info(f"Videos with incomplete categories: {len(incomplete_videos)}")
        
        return complete_videos, incomplete_videos


# ============================================================================
# PHASE 2: GROUPING STRATEGY
# ============================================================================

class GroupingStrategy:
    """Determine optimal video groupings to ensure category coverage"""
    
    def __init__(self, analysis: Dict):
        self.analysis = analysis
        self.groups = []
    
    def option_a_sequential(self):
        """OPTION A: Sequential grouping (consecutive videos)"""
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 2A: Sequential Grouping Strategy")
        logger.info("=" * 70)
        
        self.groups = [
            [1, 2],
            [3, 4],
            [5, 6],
            [7, 8],
            [9, 10],
            [11, 12],
        ]
        
        # Validate each group
        logger.info("\nValidating groups:")
        valid_groups = []
        for group_id, group_videos in enumerate(self.groups, 1):
            all_categories = set()
            total_strokes = 0
            
            for video_num in group_videos:
                if video_num in self.analysis:
                    all_categories.update(self.analysis[video_num]['categories_present'])
                    total_strokes += self.analysis[video_num]['total_strokes']
            
            has_all = len(all_categories) == 5
            status = "✓" if has_all else "✗"
            logger.info(f"{status} Dataset {group_id}: Videos {group_videos} → "
                       f"{len(all_categories)}/5 categories, {total_strokes} strokes")
            
            if has_all:
                valid_groups.append({
                    'dataset_id': group_id,
                    'videos': group_videos,
                    'categories': sorted(list(all_categories)),
                    'total_strokes': total_strokes
                })
        
        return valid_groups
    
    def option_b_smart_fill(self):
        """OPTION B: Smart merging to fill missing categories"""
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 2B: Smart Category-Fill Strategy")
        logger.info("=" * 70)
        
        # Identify category gaps for each video
        video_gaps = {}
        for video_num, info in self.analysis.items():
            all_cat = set(Config.CATEGORIES.keys())
            present = set(info['categories_present'])
            missing = all_cat - present
            video_gaps[video_num] = {
                'present': present,
                'missing': missing,
                'gap_size': len(missing)
            }
        
        # Greedy matching
        used_videos = set()
        groups = []
        group_id = 1
        
        # Sort by gap size (fill biggest gaps first)
        sorted_videos = sorted(video_gaps.items(), 
                             key=lambda x: x[1]['gap_size'], 
                             reverse=True)
        
        for video_num, gap_info in sorted_videos:
            if video_num in used_videos:
                continue
            
            if gap_info['gap_size'] == 0:
                # Already complete
                groups.append({
                    'dataset_id': group_id,
                    'videos': [video_num],
                    'categories': sorted(list(gap_info['present'])),
                    'total_strokes': self.analysis[video_num]['total_strokes']
                })
                used_videos.add(video_num)
                group_id += 1
            else:
                # Find complementary video
                group = [video_num]
                combined_categories = gap_info['present'].copy()
                
                for other_video, other_gap in sorted_videos:
                    if other_video in used_videos or other_video == video_num:
                        continue
                    
                    other_categories = other_gap['present']
                    combined = combined_categories | other_categories
                    
                    if len(combined) == 5:  # All 5 categories covered
                        group.append(other_video)
                        combined_categories = combined
                        break
                
                if len(combined_categories) == 5:
                    total_strokes = sum(
                        self.analysis[v]['total_strokes'] for v in group
                    )
                    groups.append({
                        'dataset_id': group_id,
                        'videos': sorted(group),
                        'categories': sorted(list(combined_categories)),
                        'total_strokes': total_strokes
                    })
                    for v in group:
                        used_videos.add(v)
                    group_id += 1
        
        logger.info(f"\nCreated {len(groups)} valid datasets with all 5 categories:")
        for group in groups:
            logger.info(f"  Dataset {group['dataset_id']}: Videos {group['videos']} "
                       f"→ {group['total_strokes']} strokes")
        
        return groups


# ============================================================================
# PHASE 3: DATA CONSOLIDATION
# ============================================================================

class DataConsolidation:
    """Merge selected videos into unified datasets"""
    
    def __init__(self, groups: List[Dict]):
        self.groups = groups
        self.output_dir = Config.OUTPUT_BASE
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def consolidate_all_groups(self):
        """Create unified datasets from groups"""
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 3: DATA CONSOLIDATION")
        logger.info("=" * 70)
        
        all_metadata = []
        
        for group in self.groups:
            dataset_info = self._consolidate_group(group)
            all_metadata.append(dataset_info)
        
        # Create summary
        self._create_summary(all_metadata)
        
        logger.info("\n✓ All datasets created successfully!")
        return all_metadata
    
    def _consolidate_group(self, group: Dict):
        """Consolidate one group into a dataset"""
        dataset_id = group['dataset_id']
        dataset_name = f"dataset_{dataset_id:03d}"
        dataset_dir = self.output_dir / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # Load and merge videos
        all_strokes = []
        stroke_mappings = []
        
        for video_num in group['videos']:
            csv_file = Config.CSV_PATH / f'TTVideo_{video_num}.csv'
            df = pd.read_csv(csv_file)
            
            # Add classification
            df['category'] = df['stroke_type'].apply(self._classify_stroke)
            df['original_video'] = video_num
            df['video_type'] = 'Match' if video_num <= 6 else 'Training'
            
            all_strokes.append(df)
            stroke_mappings.extend([
                {
                    'stroke_id': f"TTVideo_{video_num}_stroke_{idx}",
                    'original_video': video_num,
                    'row_index': idx
                }
                for idx in range(len(df))
            ])
        
        # Combine
        combined_df = pd.concat(all_strokes, ignore_index=True)
        
        # Save strokes
        strokes_file = dataset_dir / 'strokes.csv'
        combined_df.to_csv(strokes_file, index=False)
        
        # Save metadata
        metadata = {
            'dataset_id': dataset_id,
            'dataset_name': dataset_name,
            'source_videos': group['videos'],
            'categories': group['categories'],
            'total_strokes': group['total_strokes'],
            'actual_strokes_loaded': len(combined_df),
            'category_distribution': combined_df['category'].value_counts().to_dict(),
            'video_type_mix': combined_df['video_type'].value_counts().to_dict()
        }
        
        metadata_file = dataset_dir / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"✓ Dataset {dataset_id}: {dataset_name}")
        logger.info(f"  Source videos: {group['videos']}")
        logger.info(f"  Categories: {group['categories']}")
        logger.info(f"  Strokes: {len(combined_df)}")
        logger.info(f"  Location: {dataset_dir}")
        
        return metadata
    
    @staticmethod
    def _classify_stroke(stroke_type):
        """Classify stroke to category"""
        for category, stroke_list in Config.CATEGORIES.items():
            if stroke_type in stroke_list:
                return category
        return 'Unknown'
    
    def _create_summary(self, all_metadata):
        """Create summary of all datasets"""
        summary_file = self.output_dir / 'DATASET_SUMMARY.json'
        
        summary = {
            'total_datasets': len(all_metadata),
            'datasets': all_metadata,
            'categories': list(Config.CATEGORIES.keys()),
            'total_strokes': sum(m['actual_strokes_loaded'] for m in all_metadata)
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"\n✓ Summary created: {summary_file}")


# ============================================================================
# PHASE 4: VALIDATION & REPORTING
# ============================================================================

class ValidationReporting:
    """Validate and report on consolidated datasets"""
    
    @staticmethod
    def validate_all(output_dir: Path):
        """Validate all created datasets"""
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 4: VALIDATION & QUALITY CHECKS")
        logger.info("=" * 70)
        
        summary_file = output_dir / 'DATASET_SUMMARY.json'
        
        if not summary_file.exists():
            logger.error(f"Summary file not found: {summary_file}")
            return
        
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        
        all_valid = True
        
        for dataset_meta in summary['datasets']:
            dataset_id = dataset_meta['dataset_id']
            categories = dataset_meta['categories']
            
            # Check all 5 categories present
            has_all_5 = len(categories) == 5 and len(set(categories)) == 5
            status = "✓" if has_all_5 else "✗"
            
            logger.info(f"\n{status} Dataset {dataset_id}:")
            logger.info(f"   Categories: {categories}")
            logger.info(f"   Strokes: {dataset_meta['actual_strokes_loaded']}")
            logger.info(f"   Distribution: {dataset_meta['category_distribution']}")
            
            if not has_all_5:
                all_valid = False
                logger.warning(f"   ⚠  Missing categories: "
                              f"{set(Config.CATEGORIES.keys()) - set(categories)}")
        
        logger.info("\n" + "=" * 70)
        if all_valid:
            logger.info("✓ ALL DATASETS VALID - Ready for Stage 1")
        else:
            logger.warning("⚠  Some datasets incomplete - Review grouping strategy")
        logger.info("=" * 70)


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class DataCurationPipeline:
    """End-to-end data curation orchestrator"""
    
    def run(self, strategy: str = 'sequential'):
        """
        Run complete curation pipeline
        
        Parameters
        ----------
        strategy : str
            'sequential' (Option A) or 'smart' (Option B)
        """
        logger.info("\n")
        logger.info("╔" + "=" * 68 + "╗")
        logger.info("║  TABLE TENNIS DATA CURATION PIPELINE - SENIOR CV ENGINEER MODE  ║")
        logger.info("╚" + "=" * 68 + "╝")
        
        # Phase 1: Analysis
        analyzer = AnalysisPhase()
        analysis = analyzer.load_and_analyze()
        
        # Phase 2: Grouping
        grouper = GroupingStrategy(analysis)
        
        if strategy.lower() == 'sequential':
            groups = grouper.option_a_sequential()
        elif strategy.lower() == 'smart':
            groups = grouper.option_b_smart_fill()
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Phase 3: Consolidation
        consolidator = DataConsolidation(groups)
        metadata = consolidator.consolidate_all_groups()
        
        # Phase 4: Validation
        ValidationReporting.validate_all(Config.OUTPUT_BASE)
        
        logger.info("\n" + "=" * 70)
        logger.info("✓ PIPELINE COMPLETE")
        logger.info(f"✓ {len(metadata)} unified datasets created")
        logger.info(f"✓ Each dataset contains all 5 categories")
        logger.info(f"✓ Output directory: {Config.OUTPUT_BASE}")
        logger.info("=" * 70)


if __name__ == '__main__':
    # Run with Sequential Strategy (Option A)
    pipeline = DataCurationPipeline()
    pipeline.run(strategy='sequential')
    
    # Uncomment below to try Smart Strategy (Option B):
    # pipeline.run(strategy='smart')
