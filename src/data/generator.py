"""Stage 5: Physics-based synthetic photolithography dataset generator (LHS DOE + Fab noise).

DISCLAIMER: All generated datasets are SYNTHETIC simulations built from optical/lithography
physics models + stochastic process noise, NOT real semiconductor manufacturing fab data.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from scipy.stats import qmc

from src.physics.constants import DEFECT_THRESHOLDS, EXPOSURE_NODES
from src.physics.exposure_fem import aerial_image_contrast, bossung_cd, evaluate_defects
from src.physics.optics_tmm import build_litho_stack, get_ambient_for_node, simulate_multilayer_optics
from src.physics.process_models import tier2_process_shift
from src.physics.resolution import depth_of_focus, rayleigh_resolution


def generate_synthetic_fab_dataset(
    n_samples: int = 600,
    nodes: Sequence[str] = ("ArFi_193",),
    underlayers: Sequence[str] = ("Bare_Si", "SiO2", "PolySi", "Al_Metal"),
    illuminations: Sequence[str] = ("Conventional", "Annular", "Dipole"),
    patterns: Sequence[str] = ("Dense_1to1", "Isolated_Line"),
    metrology_noise_nm: float = 0.45,
    unmeasured_peb_drift_c: float = 0.25,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate physics-grounded synthetic photolithography dataset using Latin Hypercube Sampling.

    Includes both `cd_ideal_nm` (pure physics) and `cd_measured_nm` (physics + Fab drift/metrology noise)
    so downstream analysis and ML models transparently account for realistic process scatter.
    """
    if n_samples < 10:
        raise ValueError("n_samples must be >= 10")

    rng = np.random.default_rng(seed)
    # 9 continuous LHS factors:
    # 0: na_frac, 1: dose_ratio, 2: focus_nm, 3: pr_thick_delta, 4: barc_thick_nm,
    # 5: peb_temp_c, 6: sb_temp_c, 7: dev_time_s, 8: dev_conc_wt_pct
    sampler = qmc.LatinHypercube(d=9, seed=seed)
    u = sampler.random(n=n_samples)

    rows: List[Dict[str, object]] = []
    for i in range(n_samples):
        node_key = str(nodes[i % len(nodes)])
        node = EXPOSURE_NODES[node_key]
        if node.comparison_only:
            raise ValueError(f"Comparison-only node '{node_key}' cannot be used in DUV Fab generator")

        ul = str(underlayers[int(rng.integers(0, len(underlayers)))])
        illum = str(illuminations[int(rng.integers(0, len(illuminations)))])
        pat = str(patterns[int(rng.integers(0, len(patterns)))])
        hmds_score = float(rng.choice([0.0, 0.6, 1.0], p=[0.1, 0.2, 0.7]))

        na_val = float(node.na_min + u[i, 0] * (node.na_max - node.na_min))
        dose_val = float(node.nominal_dose_mj_cm2 * (0.78 + 0.44 * u[i, 1]))
        dof_nom = float(
            depth_of_focus(
                node.wavelength_nm, node.na_default, k2=node.k2_default, n_fluid=node.n_fluid, high_na=True
            )
        )
        focus_span = min(220.0, 1.45 * dof_nom)
        focus_val = float(-focus_span + 2.0 * focus_span * u[i, 2])
        pr_thick = float(max(60.0, node.default_pr_thickness_nm + (-20.0 + 40.0 * u[i, 3])))
        barc_thick = float(0.0 + 85.0 * u[i, 4])
        peb_temp = float(108.0 + 14.0 * u[i, 5])
        sb_temp = float(95.0 + 25.0 * u[i, 6])
        dev_time = float(40.0 + 40.0 * u[i, 7])
        dev_conc = float(2.28 + 0.20 * u[i, 8])

        ambient = get_ambient_for_node(node_key)
        stack = build_litho_stack(
            wavelength_nm=node.wavelength_nm,
            ambient_material=ambient,
            pr_thickness_nm=pr_thick,
            barc_thickness_nm=barc_thick,
            underlayer_material=ul,
            underlayer_thickness_nm=100.0,
        )
        optics = simulate_multilayer_optics(stack, node.wavelength_nm, n_z_points=60)

        min_cd = float(
            rayleigh_resolution(node.wavelength_nm, na_val, k1=node.k1_default, illumination=illum)
        )
        dof_hi = float(
            depth_of_focus(
                node.wavelength_nm,
                na_val,
                k2=node.k2_default,
                n_fluid=node.n_fluid,
                illumination=illum,
                pattern=pat,
                high_na=True,
            )
        )
        t2_ideal = tier2_process_shift(
            soft_bake_temp_c=sb_temp,
            peb_temp_c=peb_temp,
            dev_time_s=dev_time,
            dev_conc_wt_pct=dev_conc,
            target_cd_nm=node.default_target_cd_nm,
        )
        cd_ideal = float(
            bossung_cd(
                dose_val,
                focus_val,
                target_cd_nm=node.default_target_cd_nm,
                nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
                dof_scale_nm=dof_hi,
                effective_dose_factor=optics.effective_dose_factor,
                pattern=pat,
                illumination=illum,
                process_cd_bias_nm=t2_ideal["process_cd_bias_nm"],
                contrast_modifier=t2_ideal["contrast_modifier"],
            )
        )

        # Unmeasured chamber PEB drift + CD-SEM metrology noise
        peb_actual = peb_temp + float(rng.normal(0.0, unmeasured_peb_drift_c))
        t2_actual = tier2_process_shift(
            soft_bake_temp_c=sb_temp,
            peb_temp_c=peb_actual,
            dev_time_s=dev_time,
            dev_conc_wt_pct=dev_conc,
            target_cd_nm=node.default_target_cd_nm,
        )
        cd_actual = float(
            bossung_cd(
                dose_val,
                focus_val,
                target_cd_nm=node.default_target_cd_nm,
                nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
                dof_scale_nm=dof_hi,
                effective_dose_factor=optics.effective_dose_factor,
                pattern=pat,
                illumination=illum,
                process_cd_bias_nm=t2_actual["process_cd_bias_nm"],
                contrast_modifier=t2_actual["contrast_modifier"],
            )
        )
        cd_measured = max(0.0, cd_actual + float(rng.normal(0.0, metrology_noise_nm)))

        contrast = float(
            aerial_image_contrast(
                focus_val,
                node.wavelength_nm,
                na_val,
                node.n_fluid,
                node.default_target_cd_nm,
                illumination=illum,
                pattern=pat,
                k1_base=node.k1_default,
                k2_base=node.k2_default,
            )
        )
        defects = evaluate_defects(
            cd_nm=cd_measured,
            target_cd_nm=node.default_target_cd_nm,
            pr_thickness_nm=pr_thick,
            effective_dose_mj_cm2=dose_val * optics.effective_dose_factor,
            nominal_dose_mj_cm2=node.nominal_dose_mj_cm2,
            aerial_contrast=contrast,
            substrate_reflectance=optics.substrate_reflectance,
            swr_local=optics.swr_local,
            hmds_score=hmds_score,
            soft_bake_temp_c=sb_temp,
        )
        tol = node.default_target_cd_nm * DEFECT_THRESHOLDS["cd_spec_tolerance_ratio"]

        rows.append(
            {
                "node_key": node_key,
                "wavelength_nm": node.wavelength_nm,
                "na": na_val,
                "n_fluid": node.n_fluid,
                "exposure_dose_mj_cm2": dose_val,
                "focus_nm": focus_val,
                "abs_focus_nm": abs(focus_val),
                "pr_thickness_nm": pr_thick,
                "barc_thickness_nm": barc_thick,
                "peb_temp_c": peb_temp,
                "soft_bake_temp_c": sb_temp,
                "dev_time_s": dev_time,
                "dev_conc_wt_pct": dev_conc,
                "hmds_score": hmds_score,
                "underlayer": ul,
                "illumination": illum,
                "pattern": pat,
                "target_cd_nm": node.default_target_cd_nm,
                "min_cd_nm": min_cd,
                "dof_high_na_nm": dof_hi,
                "reflectance": optics.reflectance,
                "substrate_reflectance": optics.substrate_reflectance,
                "swr_local": optics.swr_local,
                "eta_abs": optics.effective_dose_factor,
                "cd_ideal_nm": cd_ideal,
                "cd_measured_nm": cd_measured,
                "cd_error_nm": cd_measured - node.default_target_cd_nm,
                "in_spec": abs(cd_measured - node.default_target_cd_nm) <= tol,
                "overall_defect_risk": defects.overall_defect_risk,
                "has_defect": len(defects.flags) > 0,
                "synthetic_data": True,
            }
        )

    return pd.DataFrame(rows)
