# Stage 4: ASIC Design

## Objective

Design a full-custom ASIC implementation of the systolic ring MD accelerator with optimized arithmetic units and memory hierarchy.

## Design Focus

### 1. Custom Arithmetic Units

**Fast Reciprocal** (`reciprocal_unit.v`)
- Newton-Raphson approximation
- 2-3 iterations for 32-bit precision
- Pipelined to 3-5 cycles latency
- ~5K gates for dual-wide unit

**Power Function** (`power_unit.v`)
- Compute r^-6 and r^-12 for Lennard-Jones
- Use logarithmic/exponential approach
- Or precomputed lookup + interpolation
- Pipelined to 5-8 cycles

**Distance Calculator** (`distance_unit.v`)
- Fast sqrt for r = sqrt(dx² + dy² + dz²)
- Newton-Raphson or Goldschmidt algorithm
- Pipelined

### 2. Memory Hierarchy

**L0: Particle Register File** (per PE)
- Current particle state (x, v, F)
- Local temporary storage
- ~200 bits per PE

**L1: Shared Position Cache**
- Read-optimized for broadcast
- Multi-port banked SRAM
- 1KB-4KB typical

**L2: Main Particle Database**
- Full state: x, v, m for all particles
- Off-chip DRAM access
- Bandwidth requirement: ~50-200 GB/s

### 3. Datapath Optimization

**Fused Operations**
- Combined force accumulation + multiplication
- Compound instructions (load-add-store)
- Reduce register pressure and memory stalls

**Pipelining**
- Deep 8-16 stage pipeline (vs FPGA's 4-6)
- Higher clock frequency (500 MHz vs 200 MHz)
- Increased throughput per unit area

### 4. Power and Area

**Area Budget** (28nm process assumed)
- Arithmetic units: ~2-3 mm²
- Memory (SRAM): ~1-2 mm²
- Logic (control + routing): ~1-2 mm²
- Total: ~5-7 mm² (10 mm² with margins)

**Power Budget** (at 500 MHz, 1.0V)
- Arithmetic: ~200-300 mW
- Memory: ~100-150 mW
- Logic: ~50-100 mW
- Total: ~400-500 mW

**Power Efficiency** (vs GPU)
- GPU: ~200 GFLOP/W (typical)
- Target: ~500 GFLOP/W (custom arithmetic)
- Energy per force: ~0.5 pJ (custom) vs 5 pJ (GPU)

## Files

- `ring_processor_asic.v`: ASIC version of ring (optimized)
- `reciprocal_unit.v`: Custom fast reciprocal
- `power_unit.v`: Custom power function unit
- `distance_unit.v`: Distance calculation with sqrt
- `sram_controller.v`: SRAM interface with multi-porting
- `pll.v`: Clock generation (on-chip PLL)
- `io_ring.v`: I/O pads and testability
- `ring_processor.sdc`: Synthesis constraints (500 MHz target)
- `power_analysis.rpt`: Post-layout power report

## Design Flow

```
ring_processor_asic.v
    ↓
[Cadence Genus] Synthesis → netlist.v
    ↓
[Cadence Innovus] Place & Route → ring_processor.def
    ↓
[Cadence Spectre] Post-layout Extraction → ring_processor.spef
    ↓
[Cadence Spectre] Post-layout Simulation → verification
    ↓
[Cadence Quantus] DRC/LVS → clean.gds
    ↓
ring_processor.gds (final layout)
```

## Performance Targets (ASIC)

| Metric | Target | vs FPGA |
|--------|--------|---------|
| Clock frequency | 500 MHz | 2.5x |
| Particle throughput | 250M/s | 10x |
| Power @ max | 400 mW | 50x lower |
| Area | 7 mm² | High efficiency |
| Energy/force | 0.5 pJ | 10x lower |

## Verification Strategy

### RTL Simulation
- Behaviorally equivalent to Python reference
- Test vectors from ring simulator
- Energy conservation checks

### Gate-Level Simulation
- Post-synthesis netlists
- Timing verification (500 MHz)
- Power analysis

### Layout Verification
- Post-extraction SPEF simulation
- IR drop analysis
- Thermal simulation

## Manufacturing & Testing

**Process**: 28 nm (TSMC or Samsung)
**Die Size**: ~10 mm × 10 mm
**Package**: 256-pin BGA or QFP

**Test Coverage**:
- Scan chains for all registers
- Built-in self-test (BIST) for memory
- Boundary scan (IEEE 1149.1)

## Estimated Cost (1K wafer)

- NRE: $5-10M (design + masks)
- Unit cost: $5-20 per chip (depends on yield)
- ROI: Breaks even at 500K units for MD workloads

## Comparison to Alternatives

| Platform | Latency | Throughput | Power | Cost |
|----------|---------|-----------|-------|------|
| GPU (A100) | 1-10 μs | 20-100 TFLOP/s | 50W | $12K |
| ASIC (custom) | 100-500 ns | 50-200 GFLOP/s | 0.4W | $10 |
| FPGA (V7) | 10-50 μs | 5-20 GFLOP/s | 5W | $2K |

*Note: ASIC wins on energy/latency for scalar workloads; GPU wins on massive parallelism*

## Next Steps

1. Finalize RTL and verify against behavioral model
2. Synthesize and analyze critical paths
3. Design custom reciprocal/power units
4. Implement memory hierarchy
5. Place and route with timing constraints
6. Extract parasitic capacitances
7. Post-layout simulation and power analysis
8. Prepare for manufacturing

## References

- **Reciprocal approximation**: Goldschmidt algorithm (Newton-Schulz)
- **Power functions**: Exponentiation by squaring
- **ASIC design**: Weste & Harris, "CMOS VLSI Design" (4th ed)
- **Power optimization**: Rabaey et al., "Digital Integrated Circuits"
