# -*- coding: utf-8 -*-
"""
T14: Temporal Evolution — Visualization Functions

Plots for temporal density matrix analysis:
- Trace evolution (intensity over time)
- Eigenvalue trajectories (semantic facets)
- Semantic drift heatmap (concepts × time)
- Entropy evolution (polysemy over time)
- Phase space trajectories (PCA projection)

Usage:
    from T14_temporal_concept import TemporalConcept
    from T14_temporal_visualization import plot_trace_evolution, plot_eigenvalue_trajectories
    
    concept = TemporalConcept(term="свобода")
    # ... add components ...
    
    plot_trace_evolution(concept).show()
    plot_eigenvalue_trajectories(concept).show()
"""

import numpy as np
from typing import Optional, List, Dict, Tuple
import warnings

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    warnings.warn("matplotlib not available; visualization functions will return None")

try:
    from T14_temporal_concept import TemporalConcept
except ImportError:
    try:
        from temporal_concept import TemporalConcept
    except ImportError:
        TemporalConcept = None


def plot_trace_evolution(concept: 'TemporalConcept', 
                        title: Optional[str] = None,
                        figsize: Tuple[int, int] = (12, 5)) -> Optional[plt.Figure]:
    """Plot Trace(ρ(t)) — intensity of experience over time.
    
    High trace = concept is "hot" (frequently mentioned, emotionally charged)
    Low trace = concept is "cold" (rarely mentioned, stable)
    
    Args:
        concept: TemporalConcept to visualize
        title: plot title (default: "Intensity Evolution: {term}")
        figsize: figure size (width, height)
        
    Returns:
        matplotlib Figure, or None if no data or matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None
    
    times, traces = concept.intensity_trajectory()
    if not times:
        print(f"No temporal data for {concept.term}")
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot trace
    ax.plot(times, traces, marker='o', linestyle='-', linewidth=2.5, 
            markersize=6, color='#2E86AB', label='Trace(ρ(t))')
    
    # Add fill under curve
    ax.fill_between(times, traces, alpha=0.2, color='#2E86AB')
    
    # Styling
    ax.set_xlabel('Time (seconds since epoch)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Trace(ρ(t)) — Intensity', fontsize=11, fontweight='bold')
    ax.set_title(title or f'Intensity Evolution: {concept.term}', 
                fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)
    
    # Add statistics
    avg_trace = np.mean(traces)
    peak_trace = np.max(traces)
    ax.axhline(avg_trace, color='red', linestyle='--', alpha=0.5, 
              label=f'Average: {avg_trace:.3f}')
    ax.text(0.02, 0.95, f'Peak: {peak_trace:.3f}\nAvg: {avg_trace:.3f}',
           transform=ax.transAxes, fontsize=10, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    return fig


def plot_eigenvalue_trajectories(concept: 'TemporalConcept',
                                 max_eigs: int = 5,
                                 title: Optional[str] = None,
                                 figsize: Tuple[int, int] = (12, 6)) -> Optional[plt.Figure]:
    """Plot eigenvalue trajectories λᵢ(t) — semantic facet evolution.
    
    Each eigenvalue represents a semantic facet:
    - λ₁(t) = dominant facet (strongest meaning)
    - λ₂(t) = secondary facet
    - etc.
    
    Crossing points = facet reordering (semantic shift)
    New emergence = polysemy increase
    Decay to zero = facet forgotten
    
    Args:
        concept: TemporalConcept to visualize
        max_eigs: maximum number of eigenvalues to plot
        title: plot title
        figsize: figure size
        
    Returns:
        matplotlib Figure, or None if no data or matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None
    
    trajectories = concept.eigenvalue_trajectories()
    if not trajectories:
        print(f"No eigenvalue data for {concept.term}")
        return None
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Color palette
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
    
    # Plot each eigenvalue trajectory
    for i in range(min(max_eigs, len(trajectories))):
        times, eigs = trajectories[i]
        color = colors[i % len(colors)]
        ax.plot(times, eigs, marker='o', linestyle='-', linewidth=2,
               markersize=5, label=f'λ_{i+1}(t)', color=color)
    
    # Styling
    ax.set_xlabel('Time (seconds since epoch)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Eigenvalue', fontsize=11, fontweight='bold')
    ax.set_title(title or f'Eigenvalue Trajectories: {concept.term}',
                fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=10, loc='best')
    
    plt.tight_layout()
    return fig


def plot_entropy_evolution(concept: 'TemporalConcept',
                          title: Optional[str] = None,
                          figsize: Tuple[int, int] = (12, 5)) -> Optional[plt.Figure]:
    """Plot von Neumann entropy S(ρ(t)) — polysemy/ambiguity over time.
    
    High entropy = polysemous (many facets, ambiguous)
    Low entropy = monosemous (single facet, clear)
    
    dS/dt > 0 = meaning becoming more ambiguous
    dS/dt < 0 = meaning clarifying
    
    Args:
        concept: TemporalConcept to visualize
        title: plot title
        figsize: figure size
        
    Returns:
        matplotlib Figure, or None if no data or matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None
    
    entropy_data = concept.entropy_evolution()
    if not entropy_data:
        print(f"No entropy data for {concept.term}")
        return None
    
    times, entropies = zip(*entropy_data)
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot entropy
    ax.plot(times, entropies, marker='s', linestyle='-', linewidth=2.5,
           markersize=6, color='#A23B72', label='S(ρ(t))')
    ax.fill_between(times, entropies, alpha=0.2, color='#A23B72')
    
    # Styling
    ax.set_xlabel('Time (seconds since epoch)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Von Neumann Entropy S(ρ(t))', fontsize=11, fontweight='bold')
    ax.set_title(title or f'Polysemy Evolution: {concept.term}',
                fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)
    
    # Add interpretation
    avg_entropy = np.mean(entropies)
    ax.axhline(avg_entropy, color='red', linestyle='--', alpha=0.5)
    ax.text(0.02, 0.95, f'Avg entropy: {avg_entropy:.3f}',
           transform=ax.transAxes, fontsize=10, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    return fig


def plot_semantic_drift_heatmap(concepts: List['TemporalConcept'],
                               title: Optional[str] = None,
                               figsize: Tuple[int, int] = (14, 8)) -> Optional[plt.Figure]:
    """Heatmap: Concepts × Time, color intensity = Trace(ρ(t)).
    
    Shows which concepts are "hot" (high trace) at which times.
    Useful for identifying discourse phases and concept interactions.
    
    Args:
        concepts: list of TemporalConcepts to visualize
        title: plot title
        figsize: figure size
        
    Returns:
        matplotlib Figure, or None if no data or matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None
    
    # Collect all timestamps
    all_times = set()
    for concept in concepts:
        all_times.update(concept._eigenvalue_history.keys())
    
    if not all_times:
        print("No temporal data in any concept")
        return None
    
    times = sorted(all_times)
    
    # Build matrix: concepts × times
    matrix = np.zeros((len(concepts), len(times)))
    for i, concept in enumerate(concepts):
        for j, t in enumerate(times):
            matrix[i, j] = concept.trace_at(t)
    
    # Normalize each row (concept) to [0, 1]
    for i in range(len(concepts)):
        row_max = np.max(matrix[i, :])
        if row_max > 1e-12:
            matrix[i, :] /= row_max
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot heatmap
    im = ax.imshow(matrix, aspect='auto', cmap='hot', interpolation='nearest')
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Normalized Trace(ρ(t))', fontsize=10, fontweight='bold')
    
    # Labels
    ax.set_xlabel('Time (seconds since epoch)', fontsize=11, fontweight='bold')
    ax.set_ylabel('Concept', fontsize=11, fontweight='bold')
    ax.set_yticks(range(len(concepts)))
    ax.set_yticklabels([c.term for c in concepts], fontsize=10)
    
    # X-axis: show only a few time labels to avoid crowding
    n_time_labels = min(10, len(times))
    time_indices = np.linspace(0, len(times) - 1, n_time_labels, dtype=int)
    ax.set_xticks(time_indices)
    ax.set_xticklabels([f'{times[i]:.0f}' for i in time_indices], fontsize=9)
    
    ax.set_title(title or 'Semantic Drift Heatmap: Concepts × Time',
                fontsize=13, fontweight='bold', pad=15)
    
    plt.tight_layout()
    return fig


def plot_embodiment_comparison(concepts: List['TemporalConcept'],
                              title: Optional[str] = None,
                              figsize: Tuple[int, int] = (10, 6)) -> Optional[plt.Figure]:
    """Bar chart comparing embodiment scores across concepts.
    
    Embodied concepts (high score):
    - High trace (frequently activated)
    - Low entropy (clear meaning)
    - Stable eigenvalues (consistent)
    
    Abstract concepts (low score):
    - Low trace (rarely activated)
    - High entropy (ambiguous)
    - Volatile eigenvalues (context-dependent)
    
    Args:
        concepts: list of TemporalConcepts to compare
        title: plot title
        figsize: figure size
        
    Returns:
        matplotlib Figure, or None if no data or matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None
    
    terms = [c.term for c in concepts]
    embodiment_scores = [c.embodiment_score() for c in concepts]
    tacit_scores = [c.tacit_knowledge_score() for c in concepts]
    
    fig, ax = plt.subplots(figsize=figsize)
    
    x = np.arange(len(terms))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, embodiment_scores, width, label='Embodiment',
                  color='#2E86AB', alpha=0.8)
    bars2 = ax.bar(x + width/2, tacit_scores, width, label='Tacit Knowledge',
                  color='#A23B72', alpha=0.8)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}', ha='center', va='bottom', fontsize=9)
    
    ax.set_xlabel('Concept', fontsize=11, fontweight='bold')
    ax.set_ylabel('Score', fontsize=11, fontweight='bold')
    ax.set_title(title or 'Embodiment vs. Tacit Knowledge',
                fontsize=13, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(terms, fontsize=10)
    ax.set_ylim([0, 1.1])
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    
    plt.tight_layout()
    return fig


def plot_phase_space_trajectory(concept: 'TemporalConcept',
                               title: Optional[str] = None,
                               figsize: Tuple[int, int] = (10, 8)) -> Optional[plt.Figure]:
    """Plot semantic evolution in 2D phase space (PCA projection).
    
    Projects ρ(t) onto first 2 principal components.
    Trajectory shows how meaning evolves through discourse.
    
    Args:
        concept: TemporalConcept to visualize
        title: plot title
        figsize: figure size
        
    Returns:
        matplotlib Figure, or None if no data or matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None
    
    if not concept._rho_snapshots or len(concept._rho_snapshots) < 2:
        print(f"Not enough snapshots for {concept.term}")
        return None
    
    # Vectorize all snapshots
    times = sorted(concept._rho_snapshots.keys())
    vectors = []
    for t in times:
        rho = concept._rho_snapshots[t]
        # Flatten to vector
        vec = rho.flatten()
        vectors.append(vec)
    
    vectors = np.array(vectors)
    
    # PCA: project to 2D
    mean = np.mean(vectors, axis=0)
    centered = vectors - mean
    cov = np.cov(centered.T)
    evals, evecs = np.linalg.eigh(cov)
    
    # Sort by eigenvalue (descending)
    idx = np.argsort(evals)[::-1]
    evecs = evecs[:, idx]
    
    # Project to first 2 components
    proj = centered @ evecs[:, :2]
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot trajectory
    ax.plot(proj[:, 0], proj[:, 1], 'o-', linewidth=2, markersize=8,
           color='#2E86AB', alpha=0.7, label='Trajectory')
    
    # Mark start and end
    ax.plot(proj[0, 0], proj[0, 1], 'go', markersize=12, label='Start',
           markeredgecolor='darkgreen', markeredgewidth=2)
    ax.plot(proj[-1, 0], proj[-1, 1], 'r*', markersize=20, label='End',
           markeredgecolor='darkred', markeredgewidth=1)
    
    # Add time labels
    for i, t in enumerate(times[::max(1, len(times)//5)]):  # label ~5 points
        idx_in_proj = times.index(t)
        ax.annotate(f't={t:.0f}', xy=(proj[idx_in_proj, 0], proj[idx_in_proj, 1]),
                   xytext=(5, 5), textcoords='offset points', fontsize=8,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.3))
    
    ax.set_xlabel(f'PC1 ({evals[idx[0]]:.1%} variance)', fontsize=11, fontweight='bold')
    ax.set_ylabel(f'PC2 ({evals[idx[1]]:.1%} variance)', fontsize=11, fontweight='bold')
    ax.set_title(title or f'Phase Space Trajectory: {concept.term}',
                fontsize=13, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    return fig


def plot_temporal_summary(concept: 'TemporalConcept',
                         figsize: Tuple[int, int] = (14, 10)) -> Optional[plt.Figure]:
    """Create a 2×2 summary plot with trace, eigenvalues, entropy, and embodiment.
    
    Args:
        concept: TemporalConcept to visualize
        figsize: figure size
        
    Returns:
        matplotlib Figure with 4 subplots, or None if matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None
    
    fig = plt.figure(figsize=figsize)
    
    # 1. Trace evolution
    ax1 = plt.subplot(2, 2, 1)
    times, traces = concept.intensity_trajectory()
    if times:
        ax1.plot(times, traces, 'o-', color='#2E86AB', linewidth=2)
        ax1.fill_between(times, traces, alpha=0.2, color='#2E86AB')
        ax1.set_ylabel('Trace(ρ(t))', fontweight='bold')
        ax1.set_title('Intensity Evolution', fontweight='bold')
        ax1.grid(True, alpha=0.3)
    
    # 2. Eigenvalue trajectories
    ax2 = plt.subplot(2, 2, 2)
    trajectories = concept.eigenvalue_trajectories()
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
    for i in range(min(3, len(trajectories))):
        times, eigs = trajectories[i]
        ax2.plot(times, eigs, 'o-', label=f'λ_{i+1}', color=colors[i], linewidth=2)
    ax2.set_ylabel('Eigenvalue', fontweight='bold')
    ax2.set_title('Semantic Facets', fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # 3. Entropy evolution
    ax3 = plt.subplot(2, 2, 3)
    entropy_data = concept.entropy_evolution()
    if entropy_data:
        times, entropies = zip(*entropy_data)
        ax3.plot(times, entropies, 's-', color='#A23B72', linewidth=2)
        ax3.fill_between(times, entropies, alpha=0.2, color='#A23B72')
        ax3.set_ylabel('Entropy S(ρ(t))', fontweight='bold')
        ax3.set_xlabel('Time', fontweight='bold')
        ax3.set_title('Polysemy Evolution', fontweight='bold')
        ax3.grid(True, alpha=0.3)
    
    # 4. Metrics summary
    ax4 = plt.subplot(2, 2, 4)
    ax4.axis('off')
    
    metrics_text = f"""
    Concept: {concept.term}
    
    Mentions: {concept.mention_count()}
    Time span: {concept.time_span() / 3600:.1f} hours
    
    Intensity:
      Average: {concept.average_intensity():.3f}
      Peak: {concept.peak_intensity():.3f}
    
    Embodiment: {concept.embodiment_score():.3f}
    Tacit knowledge: {concept.tacit_knowledge_score():.3f}
    """
    
    ax4.text(0.1, 0.9, metrics_text, transform=ax4.transAxes,
            fontsize=11, verticalalignment='top', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    fig.suptitle(f'Temporal Analysis: {concept.term}', 
                fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    return fig
