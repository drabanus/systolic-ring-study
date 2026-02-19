"""
Serial Reference MD Simulator

Naive sequential implementation - the baseline for all comparisons.
This demonstrates the O(N²) computational cost that cannot be parallelized.
"""

import numpy as np
import time
from dataclasses import dataclass
from typing import Tuple, List
import json


@dataclass
class Particle:
    """Represents a single particle in the system."""
    pos: np.ndarray  # 3D position
    vel: np.ndarray  # 3D velocity
    mass: float
    atom_type: int


class LennardJonesSystem:
    """MD system with Lennard-Jones potential."""

    def __init__(self, n_particles: int, box_size: float = 10.0):
        """
        Initialize a Lennard-Jones system.

        Args:
            n_particles: Number of particles
            box_size: Size of simulation box
        """
        self.n_particles = n_particles
        self.box_size = box_size
        self.dt = 0.001  # timestep
        self.r_cutoff = 3.0
        self.epsilon = 1.0  # LJ parameter
        self.sigma = 1.0    # LJ parameter

        # Initialize particles
        self.particles: List[Particle] = []
        self._init_particles()

        # Timing statistics
        self.force_calc_time = 0.0
        self.velocity_update_time = 0.0
        self.position_update_time = 0.0
        self.total_timesteps = 0

    def _init_particles(self):
        """Initialize particles in a random configuration."""
        np.random.seed(42)  # For reproducibility

        for i in range(self.n_particles):
            pos = np.random.uniform(0, self.box_size, 3)
            vel = np.zeros(3)
            mass = 1.0
            atom_type = 0

            self.particles.append(
                Particle(pos=pos, vel=vel, mass=mass, atom_type=atom_type)
            )

    def _lennard_jones_force(self, r: float) -> float:
        """
        Calculate LJ force magnitude for distance r.

        F = 24ε * (1/r^7 - 0.5/r^13) for r < r_cutoff, else 0
        """
        if r >= self.r_cutoff or r < 0.1:  # Avoid singularity
            return 0.0

        r_inv = 1.0 / r
        r2_inv = r_inv * r_inv
        r6_inv = r2_inv * r2_inv * r2_inv
        r12_inv = r6_inv * r6_inv

        force = 24.0 * self.epsilon * (r6_inv - 0.5 * r12_inv) * r_inv
        return force

    def _calculate_forces_naive(self) -> np.ndarray:
        """
        Calculate forces on all particles (naive O(N²) algorithm).

        This is the non-parallelizable bottleneck.
        Returns array of force vectors [N, 3].
        """
        forces = np.zeros((self.n_particles, 3))

        # O(N²) all-pairs calculation
        for i in range(self.n_particles):
            F_i = np.zeros(3)

            # Inner loop: j ≠ i
            for j in range(self.n_particles):
                if i == j:
                    continue

                # Calculate distance vector
                r_vec = self.particles[j].pos - self.particles[i].pos
                r = np.linalg.norm(r_vec)

                # Calculate force magnitude
                f_mag = self._lennard_jones_force(r)

                # Convert to vector (direction: j -> i)
                if r > 0.01:
                    f_vec = f_mag * (r_vec / r)
                    F_i += f_vec

            forces[i] = F_i

        return forces

    def _update_velocities(self, forces: np.ndarray):
        """Update velocities: v_new = v + (F/m)*dt"""
        for i in range(self.n_particles):
            a = forces[i] / self.particles[i].mass
            self.particles[i].vel += a * self.dt

    def _update_positions(self):
        """Update positions: x_new = x + v*dt"""
        for i in range(self.n_particles):
            self.particles[i].pos += self.particles[i].vel * self.dt

            # Periodic boundary conditions
            self.particles[i].pos = self.particles[i].pos % self.box_size

    def timestep(self) -> dict:
        """
        Perform one MD timestep.

        Returns timing information for this step.
        """
        step_stats = {}

        # Force calculation (the bottleneck)
        t0 = time.perf_counter()
        forces = self._calculate_forces_naive()
        t_force = time.perf_counter() - t0
        step_stats['force_calc_time'] = t_force

        # Velocity update
        t0 = time.perf_counter()
        self._update_velocities(forces)
        t_vel = time.perf_counter() - t0
        step_stats['velocity_update_time'] = t_vel

        # Position update
        t0 = time.perf_counter()
        self._update_positions()
        t_pos = time.perf_counter() - t0
        step_stats['position_update_time'] = t_pos

        # Accumulate timing
        self.force_calc_time += t_force
        self.velocity_update_time += t_vel
        self.position_update_time += t_pos
        self.total_timesteps += 1

        step_stats['total_time'] = t_force + t_vel + t_pos

        return step_stats

    def run_simulation(self, n_steps: int) -> dict:
        """
        Run simulation for n_steps timesteps.

        Returns statistics about performance.
        """
        print(f"Running serial MD simulation: {self.n_particles} particles, {n_steps} steps")

        t_start = time.perf_counter()

        step_times = []
        force_times = []

        for step in range(n_steps):
            stats = self.timestep()
            step_times.append(stats['total_time'])
            force_times.append(stats['force_calc_time'])

            if (step + 1) % max(1, n_steps // 10) == 0:
                print(f"  Step {step+1}/{n_steps}: {stats['total_time']*1000:.3f} ms")

        t_total = time.perf_counter() - t_start

        # Compute statistics
        avg_force_time = np.mean(force_times)
        avg_total_time = np.mean(step_times)

        results = {
            'n_particles': self.n_particles,
            'n_steps': n_steps,
            'total_runtime': t_total,
            'avg_timestep_ms': avg_total_time * 1000,
            'avg_force_calc_ms': avg_force_time * 1000,
            'force_calc_fraction': avg_force_time / avg_total_time,
            'throughput_steps_per_sec': n_steps / t_total,
            'theoretical_o_n2_cost': self.n_particles ** 2,
        }

        return results

    def get_statistics(self) -> dict:
        """Get timing statistics."""
        total_time = (self.force_calc_time + self.velocity_update_time +
                     self.position_update_time)

        if total_time == 0:
            return {}

        return {
            'total_timesteps': self.total_timesteps,
            'force_calc_fraction': self.force_calc_time / total_time,
            'velocity_update_fraction': self.velocity_update_time / total_time,
            'position_update_fraction': self.position_update_time / total_time,
            'total_time_sec': total_time,
        }


def demonstrate_n_squared_scaling():
    """
    Demonstrate that force calculation is O(N²).

    This shows the non-parallelizable bottleneck clearly.
    """
    print("\n" + "="*70)
    print("Demonstrating O(N²) Scaling of Force Calculation")
    print("="*70 + "\n")

    particle_counts = [10, 20, 50, 100, 200]
    n_steps = 10

    results = []

    for n in particle_counts:
        system = LennardJonesSystem(n_particles=n)
        stats = system.run_simulation(n_steps)

        force_time = stats['avg_force_calc_ms']
        results.append({
            'n_particles': n,
            'n_squared': n**2,
            'force_time_ms': force_time,
            'ops_per_force_calc': n**2,
        })

        print(f"\nN={n:3d}: {n**2:6d} operations/particle, "
              f"Force calc: {force_time:.3f} ms")

    # Check O(N²) scaling
    print("\n" + "-"*70)
    print("Scaling Analysis:")
    print("-"*70)

    for i in range(1, len(results)):
        prev = results[i-1]
        curr = results[i]

        n_ratio = curr['n_particles'] / prev['n_particles']
        n2_ratio = curr['n_squared'] / prev['n_squared']
        time_ratio = curr['force_time_ms'] / prev['force_time_ms']

        print(f"\nN: {prev['n_particles']} → {curr['n_particles']} "
              f"(ratio: {n_ratio:.1f}×)")
        print(f"  N²: ratio {n2_ratio:.1f}×")
        print(f"  Time: ratio {time_ratio:.1f}× (should match N² ratio)")

        deviation = abs(time_ratio - n2_ratio) / n2_ratio * 100
        print(f"  Deviation: {deviation:.1f}% (perfect O(N²) ≈ 0%)")

    print("\n" + "="*70)
    print("KEY INSIGHT: Time scales as O(N²) - cannot parallelize!")
    print("="*70 + "\n")

    return results


if __name__ == "__main__":
    # Quick demo
    print("Serial MD Simulator - Reference Implementation\n")

    system = LennardJonesSystem(n_particles=50)
    stats = system.run_simulation(n_steps=20)

    print("\n" + "="*70)
    print("Performance Summary")
    print("="*70)
    for key, val in stats.items():
        print(f"{key:.<40} {val:.4f}")

    # Demonstrate non-parallelizability
    demonstrate_n_squared_scaling()
