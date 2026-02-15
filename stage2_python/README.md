# Stage 2: Python Reference Implementation

## Objective

Implement a working molecular dynamics simulator with two variants:

1. **Serial MD** (`md_simulator.py`): Standard sequential implementation
2. **Ring Simulator** (`ring_simulator.py`): Software simulation of systolic ring behavior

## Learning Goals

- Verify correctness of force calculations against physics
- Measure latency and throughput of both implementations
- Understand bottlenecks in the algorithm
- Establish baseline for hardware optimization

## Files

- `md_simulator.py`: Serial reference implementation (baseline)
- `ring_simulator.py`: Systolic ring simulator in software
- `utils.py`: Shared utilities (force calculations, I/O)
- `test_accuracy.py`: Unit tests for force calculations
- `benchmark.py`: Performance comparison

## Usage

```bash
# Serial reference
python md_simulator.py --particles 128 --steps 1000 --dt 0.001

# Ring simulator
python ring_simulator.py --particles 128 --steps 1000 --stages 4

# Run tests
python test_accuracy.py

# Benchmark
python benchmark.py
```

## Implementation Strategy

### Serial Reference
1. Naive O(N²) all-pairs force calculation
2. Velocity Verlet time integration
3. Periodic boundary conditions
4. Force cutoff for efficiency

### Ring Simulator
1. Model 4-stage pipeline
2. Simulate particle flow through ring
3. Track latency and throughput
4. Verify identical results to serial version

## Performance Targets

| Metric | Serial | Ring (4-stage) | Improvement |
|--------|--------|----------------|-------------|
| Time per particle | 4 cycles | 1 cycle (after fill) | 4x |
| Memory accesses | O(N²) | O(N²) | same |
| Force calc latency | N cycles | N + 3 cycles | N/(N+3) |

## Next Steps

- Implement both simulators
- Verify physical correctness (energy conservation, etc.)
- Profile to identify bottlenecks
- Analyze memory bandwidth requirements
