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

## **Part 5: Exercise for You**

### Exercise A (Basic Understanding)
**Complete Cycle 3 (Process P2) manually:**
- Calculate distances from P0, P1, P3 to P2
- Compute forces on P2
- Update velocity and position
- Fill in the tables:

```
P2 Starting State:
  x[2] = 4.0, v[2] = 0.0

After PE1 (Forces):
  F_20 = ?
  F_21 = ?
  F_23 = ?
  F_total = ?

After PE2 (Velocity):
  v_new[2] = ?

After PE3 (Position):
  x_new[2] = ?
```

### Exercise B (System Behavior)
**Run 2 complete timesteps (8 cycles)** with the force law above:
- Track all particle positions after each cycle
- Plot x[i](t) for each particle
- Predict: Will particles equilibrate? Oscillate? Escape?

### Exercise C (Hardware Design Thinking)
**Address these design questions:**
1. How would you parallelize PE1 for 1000 particles? (It's the bottleneck)
2. What memory bandwidth is needed for shared x[] access?
3. How would you implement the synchronization barrier?

---

## **Next Steps**

Once you complete these exercises, we'll move to:
1. **Python reference implementation** of the systolic ring MD
2. **Performance modeling** (latency, throughput, memory bandwidth)
3. **FPGA prototyping** with custom force calculation unit
4. **ASIC design** with specialized arithmetic
