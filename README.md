# Systolic Ring for Molecular Dynamics

A multi-stage project to design and implement a specialized ASIC accelerator for molecular dynamics simulations using systolic ring architecture.

## Project Vision

Traditional MD simulations are parallelizable across particles/domains - a domain where GPUs and tensor clusters excel. This project targets **inherently sequential** aspects of MD:
- **Force computation bottleneck**: O(N²) pairwise interactions require sequential processing per particle
- **Sequential time integration**: Each timestep depends on the previous state
- **Scalar arithmetic intensive**: High-precision force calculations with transcendental functions

A systolic ring ASIC can achieve:
- **Custom arithmetic**: Optimized reciprocal, power, and transcendental functions for force laws
- **Pipelined throughput**: Multiple particles in-flight through computation stages
- **Memory efficiency**: Shared particle position database with streaming force computation
- **Energy efficiency**: Specialized hardware without GPU overhead

## Project Stages

### Stage 1: Pen-and-Paper Theory ✓
**Status**: In progress

Learn the fundamental systolic ring architecture through manual computation:
- 4-particle 1D system
- 4-PE ring with 4 computation stages
- Hand-trace one complete timestep
- Understand synchronization, data flow, and bottlenecks

**File**: [`STAGE1_PENANDPAPER.md`](./STAGE1_PENANDPAPER.md)

### Stage 2: Python Reference Implementation
**Status**: Pending

Implement a working MD simulator with two versions:
- **Serial reference**: Standard sequential MD code (baseline)
- **Ring simulator**: Software simulation of systolic ring behavior

Performance metrics:
- Correctness verification against physics
- Latency breakdown by stage
- Memory bandwidth requirements
- Throughput comparison (serial vs. ring pipeline)

**Directory**: `stage2_python/`

### Stage 3: FPGA Prototype
**Status**: Pending

Port to FPGA using high-level synthesis (HLS) or hand-written Verilog:
- Implement 4-stage pipeline for particle processing
- Custom force calculation block (Lennard-Jones)
- Shared memory controller with multi-port access
- Ring arbitration logic

**Directory**: `stage3_fpga/`

### Stage 4: ASIC Design
**Status**: Pending

Full-custom ASIC implementation with:
- Custom arithmetic units (fast reciprocal, power functions)
- Optimized memory hierarchy
- Pipelined particle processor
- Thermal/pressure control logic
- IO and testability infrastructure

**Directory**: `stage4_asic/`

---

## Problem Setup

### Physical Model: Lennard-Jones Molecular Dynamics

**System**: N particles in 3D box with periodic/fixed boundary conditions

**Pairwise Interaction**:
```
F_ij = 24ε [ (2/r^12) - (1/r^6) ]   for r_min < r < r_cutoff
       0                             for r ≥ r_cutoff
```

**Time Integration**: Velocity Verlet (2nd order, energy-stable)
```
v(t + dt/2) = v(t) + [a(t) * dt/2]
x(t + dt) = x(t) + v(t + dt/2) * dt
a(t + dt) = F(x(t+dt)) / m
v(t + dt) = v(t + dt/2) + [a(t+dt) * dt/2]
```

**Sequential Bottleneck**: Force calculation `F(x(t+dt))` requires all-pairs distances → O(N²) operations serially per particle

### Why Systolic Ring?

```
Naive approach:
  For each particle i:
    For each particle j ≠ i:
      Calculate distance r_ij
      Calculate force F_ij
      Accumulate force
    Update velocity
    Update position
  Latency: O(N²) per timestep

Systolic ring approach:
  Ring processes particles P0, P1, ..., P_{N-1} one per cycle
  Each particle's force is calculated in parallel through 4-stage pipeline
  Latency: O(N + 4) per timestep (after warm-up)
  Custom hardware optimizes force arithmetic
```

---

## Architecture Overview

### Systolic Ring Organization

```
                   ┌─────────────────────────────────┐
                   │     Shared Memory (Positions)    │
                   └──────────┬──────────────────────┘
                              │
         ┌──────────┬──────────┴───────┬──────────┐
         │          │                  │          │
    ┌────▼──┐  ┌────▼──┐  ┌────▼──┐  ┌────▼──┐
    │  PE0  │─▶│  PE1  │─▶│  PE2  │─▶│  PE3  │
    └────▲──┘  └───────┘  └───────┘  └───────┘
         │                            │
         └────────────────────────────┘

PE0: Particle fetch & initialization
PE1: Force calculation (N-1 pairwise distances + forces)  [CUSTOM HARDWARE]
PE2: Velocity update (Verlet half-step)
PE3: Position update (Verlet integration)
```

### Memory Organization

```
Global Particle Database:
  x[0..N-1]:  particle positions (32-bit float × 3 = 96 bits)
  v[0..N-1]:  particle velocities (32-bit float × 3 = 96 bits)
  m[0..N-1]:  particle masses (32-bit float)

Force Accumulator (per PE):
  F_acc:      accumulated force (96 bits)

Computation Constants:
  epsilon, sigma: Lennard-Jones parameters
  dt: timestep
  r_cutoff: force cutoff radius
```

---

## Design Constraints & Assumptions

### Computational
- **Precision**: 32-bit floating-point (IEEE 754) for positions/forces
- **Particle count**: Scalable, initial design targets 256-4096 particles
- **Timestep size**: Adaptive (error-controlled)
- **Force law**: Lennard-Jones with cutoff, no long-range correction

### Hardware
- **Ring stages**: 4 PEs (extensible to 8-16 for deeper pipelining)
- **Memory bandwidth**: Sufficient for all-pairs force calculation
- **Custom arithmetic**: Fast reciprocal, exp, sqrt for force/energy calculations
- **Clock frequency**: Target 500 MHz (FPGA: 100-200 MHz)

### Algorithmic
- **No constraint solvers** (SHAKE, RATTLE) in initial version
- **Thermostat**: Berendsen (simple velocity rescaling)
- **Periodic boundary conditions**: Implemented in software
- **Neighbor lists**: Optional optimization for later stages

---

## Development Workflow

```bash
# Stage 1: Read theory
cat STAGE1_PENANDPAPER.md
# Complete manual exercises

# Stage 2: Python implementation
cd stage2_python/
python md_simulator.py --particles 64 --steps 1000
python ring_simulator.py --stages 4

# Stage 3: FPGA simulation
cd ../stage3_fpga/
vivado -mode batch -source build.tcl
# Run RTL simulation

# Stage 4: ASIC design
cd ../stage4_asic/
# Synthesis, P&R, extraction with Cadence tools
```

---

## Key Files

| File | Purpose |
|------|---------|
| `STAGE1_PENANDPAPER.md` | Theory: manual computation of 4-particle system on 4-PE ring |
| `stage2_python/md_simulator.py` | Serial MD reference implementation |
| `stage2_python/ring_simulator.py` | Software simulation of systolic ring |
| `stage3_fpga/ring_processor.v` | Verilog RTL of systolic ring |
| `stage3_fpga/force_calc.v` | Custom force calculation hardware block |
| `stage4_asic/ring_processor.gds` | ASIC layout (Cadence) |

---

## References

- **Lennard-Jones Potential**: Allen & Tildesley, "Computer Simulation of Liquids" (1987)
- **Systolic Arrays**: Kung & Leiserson, "Systolic Arrays for VLSI" (1980)
- **MD Integration**: Verlet, "Computer 'Experiments' on Classical Fluids" (1967)

---

## Getting Started

1. **Read** [`STAGE1_PENANDPAPER.md`](./STAGE1_PENANDPAPER.md) carefully
2. **Work through** the 3 exercises (A, B, C) by hand
3. **Create** visualizations of particle trajectories
4. **Discuss** design insights and bottlenecks
5. **Proceed** to Stage 2 Python implementation

---

**Author**: Claude (Anthropic)
**Date**: 2026-02-15
**Status**: Stage 1 - Theory & Learning
