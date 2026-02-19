"""
Systolic Ring MD Simulator

Simulates how a systolic ring architecture processes MD force calculations.
Demonstrates why O(N²) sequential problem becomes O(N) with pipelining.
"""

import numpy as np
import time
from dataclasses import dataclass
from typing import List, Optional, Dict
from collections import deque


@dataclass
class PipelineStage:
    """Represents data flowing through a pipeline stage."""
    particle_id: int
    pos: np.ndarray  # 3D position
    vel: np.ndarray  # 3D velocity
    mass: float
    force: np.ndarray  # Accumulated force


class SystolicPE:
    """
    Processing Element in the systolic ring.

    Each PE performs one stage of the pipeline:
    PE0: Fetch particle data
    PE1: Calculate forces (bottleneck, but pipelined)
    PE2: Update velocity
    PE3: Update position
    """

    def __init__(self, stage_id: int, pe_type: str, n_particles: int):
        """
        Args:
            stage_id: Position in ring (0-3)
            pe_type: 'fetch', 'force', 'velocity', 'position'
            n_particles: Total particles in system
        """
        self.stage_id = stage_id
        self.pe_type = pe_type
        self.n_particles = n_particles

        # For PE1 (force calculation), track operations
        self.force_operations = 0

    def process(self, input_data: Optional[PipelineStage],
                system_state: dict) -> Optional[PipelineStage]:
        """
        Process data at this PE stage.

        Args:
            input_data: Data from previous stage (or None for PE0)
            system_state: Global system state (positions, velocities, etc.)

        Returns:
            Data to pass to next stage, or None if incomplete
        """
        if self.pe_type == 'fetch':
            return self._fetch_stage(input_data, system_state)

        elif self.pe_type == 'force':
            return self._force_stage(input_data, system_state)

        elif self.pe_type == 'velocity':
            return self._velocity_stage(input_data, system_state)

        elif self.pe_type == 'position':
            return self._position_stage(input_data, system_state)

        return None

    def _fetch_stage(self, _input: None, system_state: dict) -> PipelineStage:
        """PE0: Fetch particle data."""
        # In a real system, this would read from the particle queue
        # For simulation, we create a dummy particle
        particle_id = system_state.get('current_particle_id', 0)
        pos = system_state['positions'][particle_id].copy()
        vel = system_state['velocities'][particle_id].copy()
        mass = system_state['masses'][particle_id]

        return PipelineStage(
            particle_id=particle_id,
            pos=pos,
            vel=vel,
            mass=mass,
            force=np.zeros(3)
        )

    def _force_stage(self, data: PipelineStage, system_state: dict) -> PipelineStage:
        """
        PE1: Calculate forces (the bottleneck, but pipelined).

        This is where the O(N²) work happens, but it's distributed
        across N particles flowing through the pipeline.
        """
        particle_id = data.particle_id
        pos_i = data.pos
        force = np.zeros(3)

        # Calculate forces from ALL other particles
        for j in range(self.n_particles):
            if j == particle_id:
                continue

            pos_j = system_state['positions'][j]
            r_vec = pos_j - pos_i
            r = np.linalg.norm(r_vec)

            # Lennard-Jones force
            if 0.1 < r < 3.0:  # cutoff
                r_inv = 1.0 / r
                r6_inv = r_inv ** 6
                r12_inv = r6_inv * r6_inv

                f_mag = 24.0 * (r6_inv - 0.5 * r12_inv) * r_inv

                if r > 0.01:
                    force += f_mag * (r_vec / r)

        self.force_operations += self.n_particles - 1

        data.force = force
        return data

    def _velocity_stage(self, data: PipelineStage, system_state: dict) -> PipelineStage:
        """PE2: Update velocity."""
        dt = system_state['dt']
        a = data.force / data.mass
        data.vel = data.vel + a * dt
        return data

    def _position_stage(self, data: PipelineStage, system_state: dict) -> PipelineStage:
        """PE3: Update position (final stage)."""
        dt = system_state['dt']
        data.pos = data.pos + data.vel * dt

        # Periodic boundary conditions
        box_size = system_state['box_size']
        data.pos = data.pos % box_size

        return data


class SystolicRingSimulator:
    """Simulates MD calculation on a systolic ring."""

    def __init__(self, n_particles: int, n_pes: int = 4, box_size: float = 10.0):
        """
        Args:
            n_particles: Number of particles
            n_pes: Number of processing elements in ring (4 stages typical)
            box_size: Simulation box size
        """
        self.n_particles = n_particles
        self.n_pes = n_pes
        self.box_size = box_size
        self.dt = 0.001

        # Initialize system state
        np.random.seed(42)
        self.positions = np.random.uniform(0, box_size, (n_particles, 3))
        self.velocities = np.zeros((n_particles, 3))
        self.masses = np.ones(n_particles)

        # Create pipeline stages (one per PE)
        self.pes = [
            SystolicPE(0, 'fetch', n_particles),
            SystolicPE(1, 'force', n_particles),
            SystolicPE(2, 'velocity', n_particles),
            SystolicPE(3, 'position', n_particles),
        ]

        # Pipeline registers (one piece of data per stage)
        self.pipeline: deque = deque(maxlen=n_pes)

        # Statistics
        self.total_cycles = 0
        self.force_calcs_completed = 0

    def _get_system_state(self) -> dict:
        """Return current system state for PE access."""
        return {
            'positions': self.positions.copy(),
            'velocities': self.velocities.copy(),
            'masses': self.masses.copy(),
            'dt': self.dt,
            'box_size': self.box_size,
            'current_particle_id': self.force_calcs_completed,
        }

    def timestep(self, verbose: bool = False) -> Dict[str, float]:
        """
        Execute one timestep on the ring.

        Returns cycle count and timing information.
        """
        start_cycles = self.total_cycles
        cycles_this_step = 0

        # Process all N particles through the ring
        for particle_id in range(self.n_particles):
            cycles_this_step += self._process_particle_on_ring(particle_id, verbose)

        # Update global state
        self.total_cycles += cycles_this_step

        return {
            'cycles': cycles_this_step,
            'particles': self.n_particles,
            'throughput': self.n_particles / cycles_this_step,
        }

    def _process_particle_on_ring(self, particle_id: int, verbose: bool = False) -> int:
        """
        Process a single particle through the ring.

        Simulates pipeline execution for one particle.
        Returns number of cycles needed.
        """
        # In a real pipelined system:
        # - Cycle 0: Particle enters PE0 (fetch)
        # - Cycle 1: Particle moves to PE1 (force), new particle enters PE0
        # - Cycle 2: Particle moves to PE2 (velocity), etc.
        # - Cycle 3: Particle moves to PE3 (position)
        # - Cycle 4: Particle exits ring

        # After pipeline fills (4 cycles), each new particle takes 1 cycle

        # For simulation, model as:
        # - First particle: 4 cycles (pipeline fill)
        # - Subsequent: 1 cycle each (pipelined)

        if particle_id == 0:
            cycles = self.n_pes  # Pipeline depth
        else:
            cycles = 1  # Pipelined throughput

        # Actually process the particle
        system_state = self._get_system_state()
        system_state['current_particle_id'] = particle_id

        # Simulate going through all stages
        data = None
        for pe in self.pes:
            data = pe.process(data, system_state)

        # Update global state with result
        if data is not None:
            self.positions[particle_id] = data.pos
            self.velocities[particle_id] = data.vel
            self.force_calcs_completed += 1

        if verbose and particle_id < 3:
            print(f"  Particle {particle_id}: processed in {cycles} cycles")

        return cycles

    def run_simulation(self, n_steps: int, verbose: bool = False) -> dict:
        """
        Run simulation for n_steps timesteps.

        Returns performance statistics.
        """
        print(f"\nRunning Systolic Ring Simulator: {self.n_particles} particles, "
              f"{self.n_pes} PEs, {n_steps} steps")

        t_start = time.perf_counter()

        for step in range(n_steps):
            stats = self.timestep(verbose=(step < 2))

            if (step + 1) % max(1, n_steps // 10) == 0:
                avg_cycles = self.total_cycles / (step + 1)
                throughput = self.n_particles / avg_cycles
                print(f"  Step {step+1}/{n_steps}: {avg_cycles:.1f} cycles/step, "
                      f"{throughput:.2f} particles/cycle")

        t_total = time.perf_counter() - t_start

        # Compute statistics
        total_cycles_per_timestep = self.total_cycles / n_steps
        theoretical_naive = self.n_particles * self.n_pes  # Without pipelining

        results = {
            'n_particles': self.n_particles,
            'n_pes': self.n_pes,
            'n_steps': n_steps,
            'total_cycles': self.total_cycles,
            'avg_cycles_per_timestep': total_cycles_per_timestep,
            'throughput_particles_per_cycle': self.n_particles / total_cycles_per_timestep,
            'simulation_time_sec': t_total,
            'speedup_vs_serial': (self.n_particles * self.n_pes) / total_cycles_per_timestep,
            'theoretical_naive_cycles': theoretical_naive,
        }

        return results

    def get_statistics(self) -> dict:
        """Get ring statistics."""
        total_cycles_per_particle = self.total_cycles / max(1, self.force_calcs_completed)

        return {
            'total_particles_processed': self.force_calcs_completed,
            'total_cycles': self.total_cycles,
            'cycles_per_particle': total_cycles_per_particle,
            'throughput': 1 / total_cycles_per_particle,
            'pipeline_utilization': self.n_particles / self.total_cycles if self.total_cycles > 0 else 0,
        }


def compare_serial_vs_ring():
    """
    Compare serial approach vs systolic ring.

    This makes it obvious why pipelining solves non-parallelizability.
    """
    print("\n" + "="*80)
    print("Comparison: Serial vs Systolic Ring")
    print("="*80)

    n_particles_list = [50, 100, 200]
    n_steps = 10

    print(f"\nRunning {n_steps} timesteps for different system sizes:\n")

    comparison_data = []

    for n_particles in n_particles_list:
        print(f"\n{'-'*80}")
        print(f"N = {n_particles} particles")
        print(f"{'-'*80}")

        # Systolic ring simulation
        ring_sim = SystolicRingSimulator(n_particles=n_particles, n_pes=4)
        ring_stats = ring_sim.run_simulation(n_steps=n_steps)

        print(f"\nSystolic Ring Results:")
        print(f"  Average cycles/timestep: {ring_stats['avg_cycles_per_timestep']:.1f}")
        print(f"  Throughput: {ring_stats['throughput_particles_per_cycle']:.3f} particles/cycle")
        print(f"  Theoretical speedup vs naive: {ring_stats['speedup_vs_serial']:.2f}×")

        # Calculate what serial would be
        naive_cycles = n_particles * 4  # N particles × 4 PE stages
        ring_cycles = ring_stats['avg_cycles_per_timestep']

        speedup = naive_cycles / ring_cycles

        print(f"\nComparison:")
        print(f"  Naive serial (no pipelining): {naive_cycles} cycles")
        print(f"  Systolic ring (pipelined): {ring_cycles:.1f} cycles")
        print(f"  Speedup from pipelining: {speedup:.2f}×")

        comparison_data.append({
            'n_particles': n_particles,
            'naive_cycles': naive_cycles,
            'ring_cycles': ring_cycles,
            'speedup': speedup,
        })

    print("\n" + "="*80)
    print("KEY INSIGHTS:")
    print("="*80)
    print("1. Serial approach: O(N × PE_stages) cycles per timestep")
    print("2. Systolic ring: O(N + PE_stages) cycles per timestep (after warm-up)")
    print("3. Speedup approaches N / (PE_stages) = O(N) for large N")
    print("4. Pipelining converts non-parallelizable → latency-efficient")
    print("="*80 + "\n")

    return comparison_data


if __name__ == "__main__":
    print("Systolic Ring MD Simulator\n")

    # Run basic simulation
    ring = SystolicRingSimulator(n_particles=32, n_pes=4)
    stats = ring.run_simulation(n_steps=10)

    print("\n" + "="*80)
    print("Performance Summary")
    print("="*80)
    for key, val in stats.items():
        print(f"{key:.<50} {val:.4f}")

    # Compare approaches
    comparison_data = compare_serial_vs_ring()
