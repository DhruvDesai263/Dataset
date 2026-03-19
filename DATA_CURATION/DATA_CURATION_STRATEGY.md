# Data Curation Strategy: 5-Category Balanced Dataset
## Senior CV Engineer Approach

---

## 📋 PROBLEM STATEMENT

**Current State:**
- Videos 1-6: Match Rallies (may not have all 5 stroke categories)
- Videos 7-14: Training Drills (may not have all 5 stroke categories)
- **Issue:** Individual videos lack complete category representation → Feature imbalance in training

**Goal:**
- Create **6 unified datasets** (~1 per balanced dataset)
- Each dataset contains **ALL 5 stroke categories**
- Maintain **video type diversity** (Match + Training mixed)
- Enable smooth progression to Stage 1 (model training)

---

## 🎯 PROPOSED APPROACH: 4-TIER STRATEGY

### **TIER 1: Analysis Phase**
Identify which videos have which categories:

```
Video 1-6 (Match Rally):   Categories = ?
Video 7-14 (Training Drill): Categories = ?

Missing from each type? → Plan merging strategy
```

**Output:** Category distribution map

---

### **TIER 2: Grouping Strategy (3 Options)**

#### **OPTION A: Sequential Merging (Recommended)**
Group consecutive videos to ensure category diversity:

```
Unified Dataset 1: Videos 1 + 2     → Contains all categories + balanced
Unified Dataset 2: Videos 3 + 4     → Contains all categories + balanced
Unified Dataset 3: Videos 5 + 6     → Contains all categories + balanced
Unified Dataset 4: Videos 7 + 8     → Contains all categories + balanced
Unified Dataset 5: Videos 9 + 10    → Contains all categories + balanced
Unified Dataset 6: Videos 11 + 12   → Contains all categories + balanced

Remaining: Videos 13 + 14 → Validation set
```

**Advantage:** Maintains temporal continuity, preserves game flow

---

#### **OPTION B: Smart Merging (Category Fill)**
Merge strategically to fill missing categories:

```
Example:
- Video 1: Has [Serve, Foregand Chop, Backhand Chop] - Missing [Forehand Smash, Backhand Smash]
- Video 7: Has [Forehand Smash, Backhand Smash, Serve]

Merge: Videos 1 + 7 → Has all 5 categories ✓
```

**Advantage:** Guarantees 100% category coverage

---

#### **OPTION C: Stratified Sampling (Advanced)**
Random sampling with constraints:

```
From Match Rallies (1-6):  Select strokes with diverse categories
From Training Drills (7-14): Select complementary strokes
Combine → Unified datasets with balanced class distribution
```

**Advantage:** Maximum control over category ratios

---

### **TIER 3: Data Consolidation**

For each unified dataset:

1. **Extract all strokes** from constituent videos
2. **Filter to ensure ALL 5 categories present**
3. **Balance stroke counts** (if needed)
4. **Create metadata** linking back to original videos

```
Unified_Dataset_1/
├── strokes.csv (all strokes from videos 1+2)
├── metadata.json (origin, category distribution)
├── statistics.txt (counts, ratios)
└── source_mapping.json (which original video each stroke came from)
```

---

### **TIER 4: Output Structure**

Create organized directory:

```
data/
├── unified_balanced_datasets/
│   ├── dataset_001/
│   │   ├── strokes.csv
│   │   ├── metadata.json
│   │   └── visual_stats.png
│   ├── dataset_002/
│   ├── ...
│   ├── dataset_006/
│   └── DATASET_SUMMARY.csv (all 6 datasets in one table)
│
├── validation_set/
│   ├── validation_strokes.csv (from videos 13+14)
│   └── validation_metadata.json
│
└── mapping/
    ├── source_video_mapping.json
    └── category_distribution_per_dataset.json
```

---

## 💼 SENIOR ENGINEER RATIONALE

### **Why This Matters for Stage 1:**

| Issue | Impact | Solution |
|-------|--------|----------|
| **Category Imbalance** | Model overfits to common strokes | Ensure all 5 present in every dataset |
| **Low Category Frequency** | Poor minority class learning | Merge to aggregate rare strokes |
| **Video Sequence Loss** | Temporal patterns forgotten | Keep source mapping for analysis |
| **Training Stability** | Inconsistent metrics | Balanced batches from unified datasets |

### **Key Benefits:**

✅ **Reproducibility** - Documented source mapping
✅ **Scalability** - Template for future new videos
✅ **Traceability** - Know exact origin of each stroke
✅ **Quality Control** - Easy to validate category coverage
✅ **Stage 1 Readiness** - No missing categories in training batches

---

## 🔧 IMPLEMENTATION VARIANTS

### **Variant 1: Static Merging**
- Decide groups once (e.g., 1+2, 3+4, etc.)
- Create fixed unified datasets
- Use for all future training runs

**Best for:** Comparative studies, reproducibility

---

### **Variant 2: Dynamic Sampling**
- Each epoch, randomly sample balanced strokes from videos
- Ensures different combinations
- Requires more sophisticated pipeline

**Best for:** Robust model training, augmentation

---

### **Variant 3: Hybrid Balanced**
- Create baseline unified datasets (static)
- Apply within-dataset augmentation
- Combine both benefits

**Best for:** Production ML systems

---

## 📊 QUALITY CHECKS

Before moving to Stage 1, verify:

```
✓ All 6 datasets have all 5 categories
✓ Class distribution is balanced (±10% variance acceptable)
✓ Source mapping is complete (every stroke traced back)
✓ No data leakage (stroke appears in only one dataset)
✓ Temporal metadata preserved for analysis
```

---

## 🚀 EXECUTION ROADMAP

1. **Analyze** current distribution → Identify category gaps
2. **Choose strategy** (A/B/C) based on analysis
3. **Implement** merging logic
4. **Create** unified datasets
5. **Validate** quality checks
6. **Document** for reproducibility
7. **Stage 1** → Use unified datasets for training

---

## 📝 RECOMMENDED NEXT STEPS

1. Run analysis on existing 14 videos
2. Decision: Use **Option A (Sequential)** or **Option B (Smart Merging)**
3. Generate 6 unified datasets
4. Create validation/test splits
5. Proceed to Stage 1 with balanced data

---

**Result: 6 production-ready datasets, each with all 5 categories, ready for Stage 1 model training.**
