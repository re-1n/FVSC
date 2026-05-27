# -*- coding: utf-8 -*-
"""
T14: Synthetic Discourse Generator — Testing Framework

Generates synthetic discourse with timestamps to test temporal evolution.
Simulates realistic semantic drift patterns:
- Concept introduction (low trace)
- Consolidation (trace increases)
- Semantic shift (eigenvalue reordering)
- Emotional peaks (trace spikes)
- Forgetting (trace decays)

Usage:
    from T14_synthetic_discourse import generate_discourse, simulate_concept_evolution
    
    discourse = generate_discourse(
        concepts=['свобода', 'любовь', 'истина'],
        num_messages=100,
        seed=42
    )
    
    # discourse = [(timestamp, subject, verb, object, quality), ...]
"""

import numpy as np
import time
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SyntheticJudgment:
    """Synthetic judgment for testing."""
    timestamp: float
    subject: str
    verb: str
    object: str
    quality: str = "AFFIRMATIVE"
    modality: float = 1.0
    intensity: float = 0.5


def generate_discourse(concepts: List[str],
                      num_messages: int = 100,
                      base_time: float = 1000000.0,
                      time_step: float = 60.0,
                      seed: Optional[int] = None) -> List[SyntheticJudgment]:
    """Generate synthetic discourse with realistic temporal patterns.
    
    Simulates:
    - Concept introduction (first mention)
    - Consolidation (repeated mentions)
    - Semantic drift (meaning changes)
    - Emotional peaks (intensity spikes)
    - Forgetting (gaps in mentions)
    
    Args:
        concepts: list of concept terms to mention
        num_messages: total number of synthetic judgments
        base_time: starting timestamp (default: 1000000.0)
        time_step: seconds between messages (default: 60.0)
        seed: random seed for reproducibility
        
    Returns:
        List of SyntheticJudgment objects with timestamps.
    """
    if seed is not None:
        np.random.seed(seed)
    
    discourse = []
    current_time = base_time
    
    # Concept activity patterns: when each concept is mentioned
    concept_activity = {c: [] for c in concepts}
    
    # Phase 1: Introduction (first 20% of messages)
    intro_end = int(0.2 * num_messages)
    for i in range(intro_end):
        concept = np.random.choice(concepts)
        concept_activity[concept].append(i)
        current_time += time_step
    
    # Phase 2: Consolidation (middle 60% of messages)
    consolidation_end = int(0.8 * num_messages)
    for i in range(intro_end, consolidation_end):
        # Some concepts mentioned more frequently
        weights = np.random.dirichlet(np.ones(len(concepts)))
        concept = np.random.choice(concepts, p=weights)
        concept_activity[concept].append(i)
        
        # Occasional gaps (forgetting)
        if np.random.random() < 0.1:
            current_time += time_step * 10  # 10x gap
        else:
            current_time += time_step
    
    # Phase 3: Semantic shift (last 20% of messages)
    for i in range(consolidation_end, num_messages):
        # Shift focus to one or two concepts
        if np.random.random() < 0.7:
            concept = np.random.choice(concepts[:2])  # Focus on first 2
        else:
            concept = np.random.choice(concepts)
        concept_activity[concept].append(i)
        current_time += time_step
    
    # Generate judgments
    current_time = base_time
    for msg_idx in range(num_messages):
        # Find which concept(s) are mentioned in this message
        mentioned = [c for c, indices in concept_activity.items() if msg_idx in indices]
        
        if not mentioned:
            current_time += time_step
            continue
        
        for concept in mentioned:
            # Determine intensity based on phase
            if msg_idx < intro_end:
                # Introduction: low intensity, high uncertainty
                intensity = np.random.uniform(0.3, 0.6)
                modality = np.random.uniform(0.5, 0.8)
            elif msg_idx < consolidation_end:
                # Consolidation: increasing intensity
                progress = (msg_idx - intro_end) / (consolidation_end - intro_end)
                intensity = 0.5 + 0.3 * progress + np.random.normal(0, 0.1)
                modality = 0.8 + 0.2 * progress
            else:
                # Semantic shift: high intensity, potential contradictions
                intensity = 0.7 + np.random.uniform(-0.2, 0.3)
                modality = 0.9 + np.random.normal(0, 0.1)
            
            # Occasional emotional peaks
            if np.random.random() < 0.05:
                intensity = np.random.uniform(0.8, 1.0)
            
            # Occasional contradictions (quality = NEGATIVE)
            quality = "NEGATIVE" if np.random.random() < 0.1 else "AFFIRMATIVE"
            
            judgment = SyntheticJudgment(
                timestamp=current_time,
                subject="я",  # Always first person
                verb=np.random.choice(["думаю", "чувствую", "верю", "знаю"]),
                object=concept,
                quality=quality,
                modality=np.clip(modality, 0.0, 1.0),
                intensity=np.clip(intensity, 0.0, 1.0)
            )
            discourse.append(judgment)
        
        current_time += time_step
    
    # Sort by timestamp
    discourse.sort(key=lambda j: j.timestamp)
    return discourse


def simulate_concept_evolution(concept_name: str,
                              num_mentions: int = 50,
                              base_time: float = 1000000.0,
                              time_step: float = 60.0,
                              pattern: str = "consolidation") -> List[SyntheticJudgment]:
    """Simulate evolution of a single concept with specific pattern.
    
    Patterns:
    - "consolidation": intensity increases, entropy decreases
    - "drift": eigenvalues reorder (semantic shift)
    - "crisis": sudden intensity spike, then recovery
    - "forgetting": intensity decays over time
    - "oscillation": intensity oscillates (ambivalence)
    
    Args:
        concept_name: name of concept
        num_mentions: number of mentions
        base_time: starting timestamp
        time_step: seconds between mentions
        pattern: evolution pattern
        
    Returns:
        List of SyntheticJudgment objects.
    """
    judgments = []
    current_time = base_time
    
    for i in range(num_mentions):
        # Compute intensity based on pattern
        progress = i / num_mentions
        
        if pattern == "consolidation":
            # Intensity increases, variance decreases
            intensity = 0.3 + 0.5 * progress
            variance = 0.2 * (1 - progress)
        
        elif pattern == "drift":
            # Intensity stable, but meaning changes
            intensity = 0.6
            # Simulate facet reordering by changing verb
            if progress < 0.5:
                verb = "думаю"  # Epistemic
            else:
                verb = "чувствую"  # Emotional
        
        elif pattern == "crisis":
            # Spike at midpoint
            if abs(progress - 0.5) < 0.1:
                intensity = 0.9
            else:
                intensity = 0.4
            variance = 0.1
        
        elif pattern == "forgetting":
            # Intensity decays
            intensity = 0.8 * np.exp(-2 * progress)
            variance = 0.1
        
        elif pattern == "oscillation":
            # Intensity oscillates
            intensity = 0.5 + 0.3 * np.sin(4 * np.pi * progress)
            variance = 0.15
        
        else:
            raise ValueError(f"Unknown pattern: {pattern}")
        
        # Add noise
        intensity += np.random.normal(0, variance if 'variance' in locals() else 0.1)
        intensity = np.clip(intensity, 0.1, 0.95)
        
        # Occasional contradictions
        quality = "NEGATIVE" if np.random.random() < 0.05 else "AFFIRMATIVE"
        
        # Verb (may change based on pattern)
        if pattern != "drift":
            verb = np.random.choice(["думаю", "чувствую", "верю", "знаю"])
        
        judgment = SyntheticJudgment(
            timestamp=current_time,
            subject="я",
            verb=verb,
            object=concept_name,
            quality=quality,
            modality=0.8 + np.random.normal(0, 0.1),
            intensity=intensity
        )
        judgments.append(judgment)
        current_time += time_step
    
    return judgments


def create_test_scenario(scenario: str = "multi_concept") -> List[SyntheticJudgment]:
    """Create predefined test scenarios.
    
    Scenarios:
    - "multi_concept": 3 concepts with different evolution patterns
    - "semantic_crisis": single concept with sudden shift
    - "consolidation": single concept consolidating
    - "embodied_vs_abstract": embodied concept vs abstract concept
    
    Args:
        scenario: scenario name
        
    Returns:
        List of SyntheticJudgment objects.
    """
    base_time = 1000000.0
    
    if scenario == "multi_concept":
        # Three concepts with different patterns
        discourse = []
        discourse.extend(simulate_concept_evolution(
            "свобода", num_mentions=50, base_time=base_time,
            pattern="consolidation"
        ))
        discourse.extend(simulate_concept_evolution(
            "любовь", num_mentions=50, base_time=base_time + 3000,
            pattern="oscillation"
        ))
        discourse.extend(simulate_concept_evolution(
            "истина", num_mentions=50, base_time=base_time + 6000,
            pattern="drift"
        ))
        return sorted(discourse, key=lambda j: j.timestamp)
    
    elif scenario == "semantic_crisis":
        # Single concept with sudden shift
        return simulate_concept_evolution(
            "я", num_mentions=100, base_time=base_time,
            pattern="crisis"
        )
    
    elif scenario == "consolidation":
        # Single concept consolidating
        return simulate_concept_evolution(
            "смысл", num_mentions=100, base_time=base_time,
            pattern="consolidation"
        )
    
    elif scenario == "embodied_vs_abstract":
        # Embodied concept (high trace, low entropy)
        embodied = simulate_concept_evolution(
            "рука", num_mentions=50, base_time=base_time,
            pattern="consolidation"
        )
        # Abstract concept (low trace, high entropy)
        abstract = simulate_concept_evolution(
            "справедливость", num_mentions=50, base_time=base_time + 3000,
            pattern="oscillation"
        )
        return sorted(embodied + abstract, key=lambda j: j.timestamp)
    
    else:
        raise ValueError(f"Unknown scenario: {scenario}")


def print_discourse_summary(discourse: List[SyntheticJudgment]):
    """Print summary statistics of discourse."""
    print(f"\nDiscourse Summary")
    print(f"=" * 60)
    print(f"Total judgments: {len(discourse)}")
    print(f"Time span: {discourse[-1].timestamp - discourse[0].timestamp:.0f} seconds")
    print(f"  ({(discourse[-1].timestamp - discourse[0].timestamp) / 3600:.1f} hours)")
    
    # Concept frequency
    concepts = {}
    for j in discourse:
        concepts[j.object] = concepts.get(j.object, 0) + 1
    
    print(f"\nConcept frequency:")
    for concept, count in sorted(concepts.items(), key=lambda x: -x[1]):
        print(f"  {concept}: {count} mentions")
    
    # Quality distribution
    affirmative = sum(1 for j in discourse if j.quality == "AFFIRMATIVE")
    negative = sum(1 for j in discourse if j.quality == "NEGATIVE")
    print(f"\nQuality distribution:")
    print(f"  Affirmative: {affirmative} ({100*affirmative/len(discourse):.1f}%)")
    print(f"  Negative: {negative} ({100*negative/len(discourse):.1f}%)")
    
    # Intensity statistics
    intensities = [j.intensity for j in discourse]
    print(f"\nIntensity statistics:")
    print(f"  Mean: {np.mean(intensities):.3f}")
    print(f"  Std: {np.std(intensities):.3f}")
    print(f"  Min: {np.min(intensities):.3f}")
    print(f"  Max: {np.max(intensities):.3f}")


if __name__ == "__main__":
    # Example: generate multi-concept discourse
    print("Generating synthetic discourse...")
    discourse = generate_discourse(
        concepts=["свобода", "любовь", "истина"],
        num_messages=100,
        seed=42
    )
    print_discourse_summary(discourse)
    
    # Example: create test scenario
    print("\n\nCreating semantic crisis scenario...")
    crisis = create_test_scenario("semantic_crisis")
    print_discourse_summary(crisis)
