"""Defeasible, source-cited interpretations kept outside canonical evidence."""

from .assessments import AssessmentVerdict, OwnerProposalAssessment
from .generation import (
    GeneratedClaim,
    GeneratedInterpretation,
    InterpretationBackend,
    PromptSource,
    generate_interpretation_proposal,
)
from .proposals import (
    AntourageOutputType,
    InterpretationClaim,
    InterpretationLayer,
    InterpretationProposal,
    SourceCitation,
    SupportLevel,
)

__all__ = [
    "AssessmentVerdict",
    "GeneratedClaim",
    "GeneratedInterpretation",
    "InterpretationBackend",
    "AntourageOutputType",
    "InterpretationClaim",
    "InterpretationLayer",
    "InterpretationProposal",
    "OwnerProposalAssessment",
    "PromptSource",
    "SourceCitation",
    "SupportLevel",
    "generate_interpretation_proposal",
]
