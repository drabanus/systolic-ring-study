# Stage 3: FPGA Prototype

## Objective

Implement a hardware prototype of the systolic ring MD accelerator on FPGA.

## Design Components

1. **Particle Processor Ring** (`ring_processor.v`)
   - 4 pipeline stages for particle processing
   - Synchronous clock-driven operation
   - Input: particle ID, internal state
   - Output: updated particle state

2. **Force Calculation Unit** (`force_calc.v`)
   - Custom arithmetic for Lennard-Jones force
   - Fast reciprocal approximation
   - Power function implementation (r^-6, r^-12)
   - Pipelined for throughput

3. **Memory Controller** (`memory_controller.v`)
   - Multi-port shared position memory
   - Broadcast position updates
   - Streaming read access for force calculations

4. **Synchronization Logic** (`sync_controller.v`)
   - Ring arbitration
   - Particle injection/ejection
   - Timestep barrier

## Files

- `ring_processor.v`: Top-level ring architecture
- `force_calc.v`: Custom force calculation hardware
- `memory_controller.v`: Shared particle position memory
- `sync_controller.v`: Ring synchronization logic
- `testbench.v`: RTL simulation testbench
- `build.tcl`: Vivado build script

## Architecture

```
┌─────────────────┬─────────────────┬─────────────────┐
│  Force Memory   │  Position Memory│  Velocity Memory│
└────────┬────────┴────────┬────────┴────────┬────────┘
         │                 │                 │
    ┌────▼──┐          ┌────▼──┐        ┌────▼──┐
    │  PE0  │◄────────►│  PE1  │◄──────►│  PE2  │
    └────┬──┘          └────┬──┘        └────┬──┘
         │ Particle        │ Forces          │ Velocities
         │ Stream          │ (N-1 pairs)     │ Update
         │                 │                 │
      ┌──▼─────────────────▼───────────────┬─▼─┐
      │  Force Calculation Block (Custom)  │PE3│
      │  - Fast reciprocal                 │   │
      │  - Power functions                 └───┘
      │  - Distance calculation            Position
      └────────────────────────────────────┘   Update
```

## FPGA Targets

- **Xilinx Artix-7** (testing, smaller)
- **Xilinx Virtex-7** (performance, larger)
- **Intel Stratix** (alternative)

## Performance Targets

| Metric | Target |
|--------|--------|
| Clock frequency | 100-200 MHz |
| Particles per timestep | 64-256 |
| Timesteps/second | 10K-100K |
| LUT utilization | <70% |
| BRAM usage | <50% |

## Simulation Flow

```bash
# Simulate with Vivado
vivado -mode batch -source build.tcl

# Run custom testbench
xvlog testbench.v ring_processor.v force_calc.v ...
xelab testbench
xsim testbench -gui
```

## Key Challenges

1. **Memory bandwidth**: All particles' positions must be accessible simultaneously
2. **Force calculation**: Transcendental functions (reciprocal, power) optimization
3. **Precision**: 32-bit float arithmetic in hardware
4. **Synchronization**: Ring flow control and pipeline hazards

## Next Steps

- Implement ring_processor.v (basic pipeline)
- Implement force_calc.v with optimized arithmetic
- Integrate memory controller
- Verify against Python simulator
- Analyze timing and resource usage
- Optimize for throughput/area tradeoff
