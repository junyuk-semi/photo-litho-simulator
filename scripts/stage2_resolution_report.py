"""Standalone Stage 2 CLI report for Rayleigh resolution, High-NA DOF, and OAI effects."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.physics.resolution import compare_all_nodes


def main() -> None:
    print("=== Stage 2: Rayleigh Resolution & High-NA/Immersion DOF Comparison ===")
    for illum in ("Conventional", "Annular", "Dipole"):
        print(f"\n[Illumination: {illum} | Pattern: Dense 1:1 Line/Space]")
        header = f"{'Node':<14} {'λ(nm)':>6} {'NA':>5} {'n':>4} {'k1_eff':>6} {'CD_min(nm)':>11} {'DOF_hi(nm)':>11} {'DOF_par(nm)':>12} {'Note'}"
        print(header)
        print("-" * len(header))
        for r in compare_all_nodes(illumination=illum, pattern="Dense_1to1"):
            note = "comparison only" if r.comparison_only else "DUV core"
            print(
                f"{r.node_key:<14} {r.wavelength_nm:6.1f} {r.na:5.2f} {r.n_fluid:4.2f} "
                f"{r.k1_effective:6.3f} {r.min_cd_nm:11.2f} {r.dof_high_na_nm:11.1f} "
                f"{r.dof_paraxial_nm:12.1f} {note}"
            )


if __name__ == "__main__":
    main()
