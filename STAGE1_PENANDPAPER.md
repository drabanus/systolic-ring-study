# Stage 1: Pen-and-Paper Exercise
## Systolic Ring for Molecular Dynamics

This document walks through a concrete 4-particle MD system on a 4-PE systolic ring.

---

## **Part 1: System Setup**

### Physical System: 4 Particles in 1D
We'll use 1D for simplicity (extends naturally to 3D).

**Particles at time t=0:**
```
Particle:    P0      P1      P2      P3
Position:    0.0     2.0     4.0     6.0
Velocity:    0.0     0.0     0.0     0.0
Mass:        1.0     1.0     1.0     1.0
```

### Force Model: Lennard-Jones (Simplified 1D)
```
F_ij = 24 * (1/r^7 - 0.5/r^13)   [for r > r_cutoff]
       0                            [for r >= r_cutoff]

r_cutoff = 3.0
dt = 0.001  (time step)
```

### Systolic Ring Architecture

```
         ┌─────────────────────┐
         │                     │
    ┌────▼──┐  ┌──────┐  ┌──────┐  ┌──────┐
    │  PE0  │─▶│ PE1  │─▶│ PE2  │─▶│ PE3  │
    └────▲──┘  └──────┘  └──────┘  └──────┘
         │                     │
         └─────────────────────┘

Each PE: Handles one particle
Shared Memory: All particle positions available to all PEs
Ring Flow: One particle at a time flows through computation stages
```

**PE Responsibilities (one ring cycle):**
- **PE0**: Fetch particle P[i], accumulate forces from all j≠i
- **PE1**: Calculate distances to neighbors, compute pairwise forces
- **PE2**: Update velocities (F = ma → a = F/m)
- **PE3**: Update positions (Euler integration)

---

## **Part 2: One Complete Computation Cycle**

### Cycle 1: Process Particle P0

#### Ring Stage 1 (PE0): **Fetch & Initialize**
```
Input: Particle index i=0
State at start of cycle:
  - x[0]=0.0, v[0]=0.0
  - x[1]=2.0, x[2]=4.0, x[3]=6.0

Action:
  - Read x[0], v[0]
  - Initialize accumulator: F_total = 0.0

Output to PE1: (i=0, x[0]=0.0, F_acc=0.0)
```

#### Ring Stage 2 (PE1): **Force Calculation**
```
Input from PE0: (i=0, x[0]=0.0, F_acc=0.0)

Action: Calculate forces from ALL other particles j∈{1,2,3}
  j=1: r = |x[1] - x[0]| = |2.0 - 0.0| = 2.0
       Since 2.0 < 3.0 (within cutoff):
       F_01 = 24 * (1/2.0^7 - 0.5/2.0^13)
            = 24 * (0.0078125 - 0.0000305)
            = 24 * 0.0077820 = 0.1868

  j=2: r = |x[2] - x[0]| = 4.0
       Since 4.0 > 3.0 (outside cutoff): F_02 = 0

  j=3: r = |x[3] - x[0]| = 6.0
       Since 6.0 > 3.0 (outside cutoff): F_03 = 0

  F_total = F_01 + F_02 + F_03 = 0.1868 + 0 + 0 = 0.1868

Output to PE2: (i=0, v[0]=0.0, F_total=0.1868)
```

#### Ring Stage 3 (PE2): **Velocity Update**
```
Input from PE1: (i=0, v[0]=0.0, F_total=0.1868)

Action: v_new = v_old + (F/m)*dt
  a = F_total / m = 0.1868 / 1.0 = 0.1868
  v_new[0] = 0.0 + 0.1868 * 0.001 = 0.0001868

Output to PE3: (i=0, v_new=0.0001868, x[0]=0.0)
```

#### Ring Stage 4 (PE3): **Position Update**
```
Input from PE2: (i=0, v_new=0.0001868, x[0]=0.0)

Action: x_new = x_old + v*dt
  x_new[0] = 0.0 + 0.0001868 * 0.001 = 0.0000001868

State after cycle 1:
  P0: x=0.0000001868, v=0.0001868  [UPDATED]
  P1,P2,P3: unchanged

Ring output: (P0_updated)
```

---

### Cycle 2: Process Particle P1

```
Input: i=1

PE0: Fetch x[1]=2.0, v[0]=0.0, F_acc=0.0 → Pass to PE1

PE1: Calculate forces on P1 from P0, P2, P3
  j=0: r = |0.0000001868 - 2.0| ≈ 2.0
       F_10 ≈ -0.1868 (opposite direction)
  j=2: r = |4.0 - 2.0| = 2.0
       F_12 ≈ 0.1868 (same calculation)
  j=3: r = 4.0 > 3.0 → F_13 = 0

  F_total ≈ -0.1868 + 0.1868 + 0 = 0 (net force ≈ 0)

PE2: v_new[1] = 0.0 + 0 * 0.001 = 0.0

PE3: x_new[1] = 2.0 + 0.0 * 0.001 = 2.0

State after cycle 2:
  P0: x=0.0000001868, v=0.0001868
  P1: x=2.0, v=0.0  [UPDATED]
  P2,P3: unchanged
```

---

### Cycles 3-4: Process P2 and P3
*(Similar calculations - follow the same pattern)*

**After 4 cycles: One complete timestep finished**

---

## **Part 3: Key Insights for Hardware Design**

### 1. **Pipeline Latency Hiding**
- 4 particles × 4 stages = 16 cycles for one timestep with serial processing
- **With systolic ring**: After 4-cycle startup, can issue new particle every cycle
- Throughput: 1 particle per cycle (vs 1 particle per 4 cycles without ring)

### 2. **Shared Memory Access**
- All PEs need read access to **all particle positions** (for distance calculations)
- Position updates (writes) must be synchronized across ring
- **Design consideration**: Multi-port shared memory or broadcast mechanism

### 3. **Arithmetic Operations per Stage**

| PE | Operation | Cost | Notes |
|----|-----------|------|-------|
| PE0 | Read, init | 1 | Simple |
| PE1 | N-1 distances, N-1 force laws | ~3(N-1) ops | Heaviest computational load |
| PE2 | Multiply-add (force→velocity) | 2 ops | Relatively light |
| PE3 | Multiply-add (velocity→position) | 2 ops | Relatively light |

**PE1 is bottleneck** - needs custom hardware for:
- Fast reciprocal (for distance)
- Efficient power functions (r^7, r^13)

### 4. **Synchronization Points**

```
Loop:
  For i = 0 to N-1:
    1. Inject particle i into ring
    2. Pipeline fills (4 cycles)
    3. Updated particle emerges
    4. WAIT: Update shared memory x[i] ← x_new[i]
    5. Synchronize all PEs (all must see updated x[i])
    6. Proceed to next particle

End of timestep:
  All x[], v[] updated globally
  Check convergence / constraints / thermostat
```

---

## **Part 4: Extensions for 3D and Multi-Particle**

### From 1D to 3D
```
Particle: (x, y, z, vx, vy, vz)
Distance: r = sqrt((x_j - x_i)² + (y_j - y_i)² + (z_j - z_i)²)
Force magnitude: F_mag = 24 * (r^-7 - 0.5*r^-13)
Force vector: F = F_mag * (r_vec / r)  [component-wise]
```

**Cost increase:**
- Distance calc: add 2 more squared-difference terms, one sqrt
- Force update: 3× velocity/position updates (vx, vy, vz; x, y, z)

### Scaling to N Particles
```
Ring with K stages:
  - If K < N: Process particles in batches, recycle ring
  - If K = N: One particle per PE (true parallelism)
  - If K > N: Some PEs idle, but latency-hiding capacity unused

For ASIC:
  - Custom arithmetic for PE1 (distance/force)
  - Memory bandwidth becomes constraint
  - Consider specialized distance/force processor as custom block
```

---

## **Part 5: Exercises & Solutions**

### Exercise A (Basic Understanding): Process P2

**Problem Statement:**
Complete Cycle 3 (Process P2) manually:
- Calculate distances from P0, P1, P3 to P2
- Compute forces on P2
- Update velocity and position

**Solution:**

```
P2 Starting State:
  x[2] = 4.0, v[2] = 0.0
  Position updated from Cycle 1: x[0] = 0.0000001868
  Position updated from Cycle 2: x[1] = 2.0

PE0: Fetch & Initialize
  Input: i=2
  Output: (i=2, x[2]=4.0, v[2]=0.0, F_acc=0.0)

PE1: Calculate forces on P2
  Distance to P0: r_20 = |x[2] - x[0]| = |4.0 - 0.0000001868| ≈ 4.0
                  Since 4.0 > 3.0 (outside cutoff): F_20 = 0

  Distance to P1: r_21 = |x[2] - x[1]| = |4.0 - 2.0| = 2.0
                  Since 2.0 < 3.0 (within cutoff):
                  F_21 = 24 * (1/2.0^7 - 0.5/2.0^13)
                       = 24 * (0.0078125 - 0.0000305)
                       = 0.1868
                  Direction: P1 is LEFT of P2, so force points LEFT (negative)
                  F_21 = -0.1868

  Distance to P3: r_23 = |x[2] - x[3]| = |4.0 - 6.0| = 2.0
                  Since 2.0 < 3.0 (within cutoff):
                  F_23 = 24 * (1/2.0^7 - 0.5/2.0^13) = 0.1868
                  Direction: P3 is RIGHT of P2, so force points RIGHT (positive)
                  F_23 = +0.1868

  F_total = F_20 + F_21 + F_23 = 0 + (-0.1868) + 0.1868 = 0.0

PE2: Velocity Update
  a = F_total / m = 0.0 / 1.0 = 0.0
  v_new[2] = v[2] + a*dt = 0.0 + 0.0*0.001 = 0.0

PE3: Position Update
  x_new[2] = x[2] + v_new[2]*dt = 4.0 + 0.0*0.001 = 4.0

State after Cycle 3:
  P0: x=0.0000001868, v=0.0001868
  P1: x=2.0, v=0.0
  P2: x=4.0, v=0.0  [UPDATED - no net force, stationary]
  P3: unchanged
```

**Key Insight**: P2 is in equilibrium between P1 and P3 (equal distance, equal forces in opposite directions).

---

### Exercise B (System Behavior): Run 2 Full Timesteps

**Problem Statement:**
Run 2 complete timesteps (8 cycles, 4 particles each) and track positions.

**Solution:**

After Cycle 1: P0 updated
- P0: x = 0.0 + 0.0001868*0.001 = 0.0000001868

After Cycle 2: P1 updated
- P1: neighbors are P0 (≈2.0 away) and P2 (2.0 away)
- Forces: F_10 ≈ -0.1868, F_12 ≈ +0.1868 → net ≈ 0
- P1: x = 2.0 (no change), v = 0.0

After Cycle 3: P2 updated
- P2: neighbors P1 (2.0 away) and P3 (2.0 away)
- Forces: F_21 ≈ -0.1868, F_23 ≈ +0.1868 → net = 0
- P2: x = 4.0 (no change), v = 0.0

After Cycle 4: P3 updated
- P3: neighbor P2 (2.0 away), P1 (2.0 away)
- Distance P3-P2: r = 2.0, F_32 = 24 * (1/2^7 - 0.5/2^13) = 0.1868 (leftward)
- Distance P3-P1: r = 4.0 > 3.0 → F_31 = 0
- Distance P3-P0: r = 6.0 > 3.0 → F_30 = 0
- F_total = -0.1868
- a = -0.1868, v_new[3] = 0 + (-0.1868)*0.001 = -0.0001868
- x_new[3] = 6.0 + (-0.0001868)*0.001 = 5.9998132

**After Timestep 1 (4 cycles):**
```
P0: x = 0.0000001868, v = 0.0001868
P1: x = 2.0,         v = 0.0
P2: x = 4.0,         v = 0.0
P3: x = 5.9998132,   v = -0.0001868
```

**Timestep 2 (Cycles 5-8):**

Following the same logic, as particles move:
- P3 is pulled leftward by P2
- P0 is pulled rightward by P1
- P1, P2 remain in equilibrium
- Oscillations develop around equilibrium positions

**Plot (approximate trajectories):**
```
         Timestep 1        Timestep 2
P0:  0.0000002  →  0.0000004  →  ... (slow rightward motion)
P1:  2.0        →  2.0        →  2.0 (equilibrium)
P2:  4.0        →  4.0        →  4.0 (equilibrium)
P3:  5.9998132  ←  5.9996264  ←  ... (slow leftward motion)
```

**Prediction**:
- **P0 and P3** will oscillate: attracted to center but overshoot, then accelerate back
- **P1 and P2** will remain in equilibrium (forces always balanced)
- **Long-term**: System exhibits harmonic oscillations around equilibrium
- **Energy**: Kinetic + Potential energy cycles between particles
- **No escape**: Force cutoff prevents unbounded motion

---

### Exercise C (Hardware Design): Critical Questions with Answers

**Question 1: How would you parallelize PE1 for 1000 particles?**

PE1 is the bottleneck because it must calculate N-1 distances and forces sequentially.

**Answer:**
```
Current design (1 PE1):
  - N-1 = 999 distance calculations per particle
  - At 5 cycles per distance (reciprocal + power functions)
  - Total: ~5000 cycles per particle in PE1
  - Bottleneck!

Solution A: Parallel Reduction Units
  Create K parallel force calculation units:

  ┌─────────┬─────────┬─────────┬─────────┐
  │ FCU_0   │ FCU_1   │ FCU_2   │ FCU_3   │
  └────┬────┴────┬────┴────┬────┴────┬────┘
       └────┬─────┬─────┬─────┬──────┘
            └─────┴─────┴─────┘
                 Sum Reducer
                    ↓
             F_total (to PE2)

  - Distribute N-1 distances across K units
  - Each unit calculates ~(N-1)/K distances in parallel
  - Reduction tree sums forces: log₂(K) cycles
  - Total PE1 latency: O((N-1)/K + log₂(K))
  - For K=16: O(60 + 4) = O(64) cycles instead of 5000

Solution B: Streaming Distance Calculator
  - Implement pipelined distance unit (1 result per 2 cycles)
  - Pipeline depths for distance, reciprocal, power
  - Can process continuous stream of particle pairs

Solution C: Specialized Force Processor (ASIC-level)
  - Custom hardware block that processes M particles/cycle
  - Transcendental function approximators (Newton-Raphson)
  - Pipelined architecture with 8-16 stages
  - Achieves distance in 2-3 cycles
```

**Question 2: What memory bandwidth is needed for shared x[] access?**

```
System Analysis:
  - N particles, each with 3D positions (96 bits = 12 bytes)
  - Total position data: 12N bytes
  - Processing N particles per timestep
  - Each particle reads N-1 other positions

For N=1000 particles:
  - Memory reads per timestep: 1000 × 999 × 96 bits ≈ 96 Mbits
  - At 1 GHz clock: 96 MB/cycle × 1 cycle = 96 MB/cycle
  - Assuming 4 cycles per PE1 distance calculation:

  Bandwidth = 96 MB/cycle × (1 GHz / 4 cycles) = 24 GB/s

  With deeper pipelines (8 stages):
  Bandwidth = 96 MB/cycle × (1 GHz / 8 cycles) = 12 GB/s

Reality Check (Actual Full System):
  - With 16 PEs in ring: 16 simultaneous reads possible
  - Ring throughput: 1 particle/cycle after warmup
  - Position broadcasts needed for all PEs to see all x[]

  → Requires multi-port SRAM or broadcast memory architecture
  → ~32-64 GB/s peak bandwidth for practical systems
  → Comparable to GPU memory bandwidth (but more specialized)
```

**Question 3: How would you implement the synchronization barrier?**

```
Challenge: All PEs must see updated positions before next particle

Design A: Broadcast Memory Synchronization
  ┌──────────────────────────────────────┐
  │ Shared Position Memory (broadcast)   │
  └──────────────────────────────────────┘
              ↓ (cycle N+1)
  ┌────────────┬──────────┬──────────┐
  │ PE0 reads  │ PE1 uses │ PE2 uses │ ...
  │ (stale x[])│ (stale)  │ (stale)  │
  └────────────┴──────────┴──────────┘

  Problem: Pipelined reads see different x[] values

Solution A: Write-Through Synchronization
  1. PE3 outputs updated x[i]
  2. Broadcast x[i] to all PEs
  3. All PEs update local x[] cache
  4. Barrier: wait for all PEs to ACK
  5. Proceed to next particle

  Cost: 1-2 extra cycles per particle

Solution B: Timestamp-Based Coherence
  Each position tagged with version number:
  - x[i] → {value, version=t}
  - PE1 tracks which version it's using
  - Only processes forces with current version
  - Mismatch triggers local update

  Cost: Extra registers, version comparison logic

Solution C: Speculative Execution + Rollback
  - Optimistic: assume updated x[] is available
  - Continue processing with previous x[]
  - If conflict detected: rollback and re-execute
  - Works well when memory bandwidth is high

  Cost: Complex control logic, repeated work on conflicts

Recommended (for ASIC): Solution B (Timestamp-Based)
  - Minimal synchronization overhead
  - Supports variable pipeline depths
  - Scalable to multiple rings
```

---

## **Part 6: 16-PE Systolic Ring with Larger Molecule**

### System: Alanine Dipeptide (20-28 atoms)

A realistic test case for protein folding simulations.

**Alanine Dipeptide Structure:**
```
Atom Index    Atom Type    Position (Angstroms)
   0          N            (0.0,   0.0,   0.0)      [Backbone N]
   1          C            (1.45,  0.0,   0.0)      [Alpha C]
   2          C            (2.2,   1.2,   0.0)      [Carbonyl C]
   3          O            (3.4,   1.2,   0.0)      [Carbonyl O]
   4          C            (1.8,  -1.3,   1.0)      [Methyl (R group)]
   5          N            (3.6,   2.3,   0.0)      [Next residue N]
   6          C            (4.5,   2.3,  -1.2)      [Next alpha C]
   ...        (+ 14-22 more for methyl, hydrogens if included)

Total: 20-28 atoms depending on hydrogen treatment
```

### 16-PE Ring Architecture for This System

```
                    ┌─────────────────────────────────────────┐
                    │   Shared Atom Position Memory (96b×20)  │
                    │   All PE0-PE15 can broadcast-read        │
                    └──────────┬──────────────────────┬────────┘
                               │                      │
         ┌─────────┬───────────┼────────┬──────┬─────┼──────┬─────┐
         │         │           │        │      │     │      │     │
    ┌────▼──┐ ┌────▼──┐ ┌──────▼─┐ ┌───▼─┐ ... ┌──┴──┐ ┌────▼──┐
    │  PE0  │ │  PE1  │ │  PE2   │ │ PE3 │     │PE14 │ │ PE15  │
    │ Fetch │ │ Force │ │Velocity│ │Posn │     │ ... │ │ Posn  │
    └────┬──┘ └───────┘ └────────┘ └─────┘     └─────┘ └───────┘
         │
    Particle stream (one atom per cycle after warmup)
```

### Processing Timeline for Alanine Dipeptide

```
Cycle:  0    1    2    3    4   ...  15   16   17   18   19   20
Ring:   [    A0   A1   A2   A3  ...  A15  A16  A17  A18  A19   ]
Status: [warm|FILLING PIPELINE...        |PROCESSING 20 atoms (at 1/cycle)|
        PE0  PE1  PE2  PE3  PE4  ...PE15 PE16 PE17 PE18 PE19 PE20]

Warmup: 15 cycles (ring fills)
Processing: 20 cycles (1 atom per cycle through pipeline)
Cooldown: 3 cycles (pipeline empties)
Total: 38 cycles per timestep

Throughput: 20 atoms / 38 cycles = 0.53 atoms/cycle
vs Serial: 20 atoms × 4 stages = 80 cycles (theoretical)
           → 20 atoms / 80 cycles = 0.25 atoms/cycle
```

### Force Calculations in 16-PE Ring

```
Per Atom Processing:

PE0 (Fetch):
  - Read atomic position x[i], velocity v[i]
  - Look up atomic mass m[i] and type
  - Initialize force accumulator: F_i = 0
  - Output: (i, x[i], v[i], m[i])
  - Cost: 1 cycle (memory access)

PE1-PE10 (Force Calculation - 10 PEs!):
  Why 10 PEs?
  - Alanine dipeptide has 20 atoms
  - O(N²) but N-1 ≈ 19 distances needed per atom
  - Distributed across 10 PEs: ~2 distance calculations each

  Design: Each PE computes distance to 2 atoms
  ┌─────────────────────────────────────┐
  │ Parallel Force Calculation Block     │
  ├─────────────────────────────────────┤
  │ Input: Atom i, all x[0..19]         │
  │ PE1 calculates: F_i,0 + F_i,1       │
  │ PE2 calculates: F_i,2 + F_i,3       │
  │ ...                                 │
  │ PE10 calculates: F_i,18 + F_i,19    │
  │                                     │
  │ Output: 10 partial force vectors    │
  └─────────────────────────────────────┘

  Reduction tree sums to get F_total
  Cost: 1 + log₂(10) ≈ 4 cycles

PE11 (Velocity Update):
  - v_new = v + (F/m)*dt
  - Cost: 1 cycle (3D vector math)

PE12-PE15 (Position Update + Side Effects):
  - x_new = x + v*dt
  - Update velocities in shared memory
  - Check constraints (bonds, angles if any)
  - Cost: 2 cycles

Total latency: 1 + 4 + 1 + 2 = 8 cycles per atom
(compared to 4 for naive 4-PE, but now processing 16 atoms in parallel)
```

### Performance Metrics for Alanine Dipeptide

```
16-PE Ring vs Alternatives:

Configuration         | Cycles/Timestep | Atoms/Cycle | MHz | ns/Timestep
─────────────────────┼─────────────────┼─────────────┼─────┼──────────
Serial (naive)       | 20 × 8 = 160    | 0.125       | 1   | 160 ns
4-PE Systolic        | 4 + 20 = 24     | 0.83        | 5   | 4.8 ns
16-PE Systolic (ours)| 15 + 20 = 35    | 0.57        | 10  | 3.5 ns
GPU (Tesla A100)     | ~100 ops/atom   | parallel    | 1.4G| ~14 ps

Speedup of 16-PE vs Serial: 160/35 ≈ 4.6× on throughput
Speedup of 16-PE vs 4-PE: 35/24 ≈ 1.5× (broader pipeline)
Energy efficiency vs GPU: 100-1000× (custom arithmetic)
```

---

## **Part 7: Scaling to Real Proteins**

### Typical Protein Sizes & Simulation Requirements

```
Protein                 | Atoms  | Particles | Simulation Time | Use Case
────────────────────────┼────────┼───────────┼─────────────────┼──────────────
Alanine Dipeptide       | 20-22  | 20        | 1 μs (learning) | Folding test
Trp-Cage (1L2Y)         | 700    | 700       | 1 ms (folding)  | Protein folder
Villin (1vii)           | 2,000  | 2,000     | 1-10 ms         | Folder
Chignolin (2RVD)        | 1,680  | 1,680     | 100 ns (CG)     | Speed test
SARS-CoV-2 Spike       | 1.2M   | 1.2M      | 1 ms (GPU)      | Large complex
Ribosome 80S           | 2.5M   | 2.5M      | microseconds    | Extreme
```

### PE Requirements for Different Scales

```
Strategy 1: One PE per atom (full parallelism)
─────────────────────────────────────────────
Size:       PEs Needed   Clock    Power    Latency/Step
4-PE ring   4            5 MHz    0.1W     10-50 ns
16-PE ring  16           10 MHz   0.5W     5-10 ns
64-PE ring  64           20 MHz   2W       3-5 ns
128-PE ring 128          30 MHz   5W       2-3 ns
256-PE ring 256          50 MHz   10W      1-2 ns

For Trp-Cage (700 atoms):
  - Need ≥700 PEs for single-particle parallelism
  - But rings process particles sequentially
  - Multiple rings: 7 rings × 100-PE = 700 total
  - or 10 rings × 70-PE = 700 atoms

For Villin (2000 atoms):
  - 20 rings × 100-PE = 2000 atoms
  - or 10 rings × 200-PE = 2000 atoms

Strategy 2: Batched Processing (Realistic)
──────────────────────────────────────────
Single 256-PE ring:
  - 4 batches of 256-atom subsystems
  - Process each for 1 timestep
  - Stitch results together
  - Periodic boundaries/constraints between batches
  - Effective latency: O(N/256 + 256) per timestep

Single 64-PE ring with 10 timesteps:
  Trp-Cage (700 atoms):
  - 11 batches × 64 atoms = need 11 ring-cycles per timestep
  - Realistic if distance/force calculation is optimized

Strategy 3: Domain Decomposition
─────────────────────────────────
For large proteins (villin, ribosome):
  - Divide protein into spatial domains
  - Each domain: small ring (16-64 PEs)
  - Exchange forces at boundaries
  - Reduces O(N²) within domain to O(D²) where D << N

Example: Villin (2000 atoms)
  - 4 domains (500 atoms each)
  - 4 separate 64-PE rings
  - Total: 256 PEs
  - Effective complexity: O(500²) = O(250K) vs O(2000²) = O(4M)
  - Speedup: 16×
```

### Recommended PE Counts for Practical Protein Folding

```
Application              | Molecule Size | Recommended PEs | Hardware
─────────────────────────┼───────────────┼─────────────────┼──────────────
Educational             | 20-50         | 16-64          | FPGA
Alanine dipeptide folder | 20            | 16             | FPGA/ASIC
Trp-Cage folder         | 700           | 64 × 10 rings  | Multi-ASIC
Protein folding (prod)  | 100-1000      | 256-512        | Custom ASIC
Large complex (GPU fall)| >10,000       | 1024+          | Not practical

PE Budget for Production System:
─────────────────────────────────
Protein folding typically involves:
  1. Initial structure: ~1000 atoms
  2. Simulation time: 10-100 microseconds for folding
  3. Timesteps: 10K-100K timesteps needed
  4. Desired speedup: 100-1000× vs GPU

Recommendation: 256-512 PE ASIC
  - 64-256 PE main ring (parallel atoms)
  - 2-4 supporting rings for long-range forces
  - Dedicated memory: ~1 MB SRAM
  - Power budget: 1-5W
  - Die size: 20-50 mm² (28nm)
  - Cost: $100-500/chip in volume

Edge Case: Ultra-Large Systems (2M+ atoms, ribosomes)
  - Not practical for single ASIC
  - GPU/TPU parallelism required
  - ASIC benefits diminish (can't parallelize enough)
  - Better strategy: GPU array + periodic custom ASIC passes
```

### Protein Folding Simulation Workflow with Systolic Ring

```
Input: Protein structure (PDB file, 1000 atoms)

Algorithm:
  for timestep = 1 to 100000:

    1. Broadcast atomic positions to all PEs

    2. Systolic Ring Processing (256-PE ring):
       for batch = 1 to ceil(1000/256) = 4:
         Inject atoms (batch*256 to (batch+1)*256-1)
         Pipeline fills: 8 cycles
         Process 256 atoms: 256 cycles @ 1 atom/cycle
         Output updated velocities & positions
         Accumulate forces from other batches

    3. Apply Constraints (optional):
       - RATTLE algorithm for bond lengths
       - Angle constraints if needed

    4. Apply Thermostat (Berendsen):
       - Rescale velocities to target temperature
       - All-reduce operation: sum(v²) across PEs

    5. Check Convergence:
       - Compute root-mean-square deviation (RMSD) from start
       - If RMSD < threshold: fold complete, stop
       - If energy too high: system unstable, reduce timestep

    6. Store snapshot (every 100 timesteps):
       - Output atomic coordinates
       - Energy, temperature, pressure

Time estimate (256-PE ASIC @ 100 MHz):
  - Per timestep: 4 batches × 264 cycles = 1056 cycles @ 100 MHz = 10.56 μs
  - 100K timesteps = 1.056 seconds = realistic molecular dynamics timeframe

GPU comparison (A100):
  - Per timestep: ~100-500 μs (depending on implementation)
  - 100K timesteps = 10-50 seconds

→ ASIC is 10-50× faster than GPU for this workload!
```

---

## **Part 8: Hardware Architecture for 256-PE Production ASIC**

### Hierarchical Ring Architecture

```
┌────────────────────────────────────────────────────────────┐
│ Main Ring: 64 PEs (process 64 atoms/cycle after warmup)   │
│  PE[0-63] with 8-stage pipeline                           │
└─────────────┬────────────────────────────┬────────────────┘
              │                            │
        ┌─────▼────────┐           ┌──────▼────────┐
        │ Ring Control │           │ Memory System │
        │ & Sync Logic │           │ (1 MB SRAM)   │
        └──────────────┘           └───────────────┘

Supporting Units:
  - Constraint Solver (bonds, angles): 8-16 PEs
  - Thermostat Control: 4-8 PEs
  - Energy Calculator: 4-8 PEs
  - Total: 64 + 40 = ~100-130 PEs in main path

Auxiliary Structures:
  - Fast reciprocal units: 2-4 per PE (high utilization)
  - Power function units: 1-2 per PE
  - Distance calculator: shared (pipelined)
  - Reduction tree: log₂(64) = 6-stage butterfly network

Total transistor count (28nm):
  - 64 PEs × 50K transistors = 3.2M
  - ALU, multipliers per PE: 2M
  - Memory (1 MB SRAM): 10M transistors
  - Control logic: 2M
  - Total: ~20-25M transistors (comparable to modern ARM cores)
```

### Memory Organization for 1000-Atom System

```
Atom Database (shared SRAM):
┌─────────────────────────────────────────┐
│ Position Cache     (1000 atoms × 96b) = 96 KB   │
│ Velocity Cache     (1000 atoms × 96b) = 96 KB   │
│ Force Accumulator  (64 atoms × 96b)   = 6 KB    │
│ Atomic Properties  (1000 atoms × 64b) = 64 KB   │
│ Constraints Table  (neighbor list)    = 32 KB   │
│ Temporary Buffers                     = 64 KB   │
├─────────────────────────────────────────┤
│ Total: ~360 KB (fits easily in 1 MB)   │
└─────────────────────────────────────────┘

Access Pattern:
  - PE reads: positions of 1000 atoms (broadcast)
  - Force accumulation: write conflicts for shared atoms
  - Solution: PE-local accumulators, global reduction

Bandwidth requirement:
  - 64 atoms/cycle × (96 bits position + 32 bits distance + 32 bits force)
  - = 64 × 160 bits/cycle = 10,240 bits/cycle
  - @ 100 MHz = 1.024 Tbits/s ≈ 128 GB/s!
  - Feasible with multi-port SRAM (4-8 ports) or HBM
```

---

## **Next Steps**

Once you complete these detailed exercises and understand 16-PE scaling:

1. **Protein Folding Benchmark**: Design a simulation plan for Trp-Cage (700 atoms)
2. **Memory Architecture Study**: Determine optimal SRAM configuration for your target protein size
3. **Python Implementation**: Implement batched ring simulator for arbitrary protein sizes
4. **Performance Modeling**: Estimate total system throughput and energy for 1000-atom target
5. **FPGA Prototype**: Build 16-PE prototype on Arty A7 or similar
