# Knowledge tracing and readiness

For prior mastery p, slip s and guess g, a correct observation yields p(1-s)/(p(1-s)+(1-p)g). An incorrect observation yields ps/(ps+(1-p)(1-g)). A learning transition follows: posterior + (1-posterior) × .08, bounded to [.01,.99]. Slip varies from .08 to .16 by difficulty; MCQ guess=1/option count. Teacher-confirmed open-response viva uses guess=.1, difficulty 2 and correctness at a confirmed score of 70 or higher. These are illustrative, uncalibrated parameters.

Repeated answers to the same MCQ within 24 hours have delta weight max(.15, 1/(1+prior recent answers)). A hinted correct answer multiplies that weight by .35. The update is prior + weight × (raw posterior − prior). Repetition discount reduces but does not eliminate correlated-evidence inflation. Hints do not reduce the negative evidence of an incorrect answer. Elapsed question time is stored and reported, not used as an ability signal.

Answers retain prior/posterior, selected option, correctness, elapsed time, hint use and weight. Atomic run cursor claims prevent double submission; optimistic mastery comparisons reject conflicting concurrent updates. Viva requires one teacher review before affecting mastery. Provisional AI output cannot change mastery or official grades.

Mastery confidence n/(n+8), capped at .95, remains an attempt-count proxy rather than a calibrated uncertainty interval. Wrong answers create possible misconception evidence; question labels are not a proven semantic diagnosis. A prerequisite-first traversal orders weak concepts. Reviews are scheduled +1,+3,+7 days for lower mastery and +3,+7,+14 for mastery ≥.8. Marking tasks/reviews done does not change mastery.

Readiness uses fixed weights: 40% estimated mastery, 15% observed-topic coverage, 15% MCQ accuracy, 15% mean of the last three completed mock exams, 10% assessed topics at 60%+ mastery, and 5% practice recency. Recency decays linearly to zero over 30 days and is averaged across the syllabus. Unanswered mock questions count as incorrect. Missing MCQ/mock evidence is displayed as unavailable and contributes zero; it is not an invented assessment score. The UI displays factors, weights and contributions. This is a planning indicator, not a validated prediction of an exam grade. Demo priors remain synthetic with zero initial observations.

## Formal viva evidence (0.3)

Teacher-finalized formal marks update each mapped question's concept once using a conservative 0.35 evidence weight. This is an illustrative, uncalibrated policy, not a validated estimate of student ability. Follow-up turns never count as additional questions. Provisional AI marks and explicitly auto-finalized sessions do not update this mastery path. Confirmed results remain distinguishable from proposals in the UI and API.

## Conservative quiz updates (0.4)

The BKT-derived target is now tempered to 15% of its delta, capped at +0.03/-0.05 per observation, then further discounted for repeats and hints. Quiz increases cannot pass 0.79 without 12 distinct questions across three run IDs; crossing 0.89 also requires two UTC practice dates. The model caps at 0.97. Existing probabilities above a gate are retained rather than retroactively rewritten. Teacher-confirmed viva also uses the smaller bounded update; formal viva applies its existing 0.35 weight. Quiz percentage measures that paper's accuracy, not concept completion. These policy thresholds require real educational calibration.
