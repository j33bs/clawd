# DALI Phase One Handoff - 2026-03-09

## Intent
This handoff supersedes the earlier incremental UE5 scene-builder direction.

The new implementation target is:
- offline generation pipeline
- single point -> bacteria -> archetypes -> fantasy landscape
- Unreal used as the assembly/presentation layer
- no runtime AI in Phase One

## Clean State
- `dali-fishtank.service` is stopped
- current control state is forced `off`
- no UE display process is left running
- nothing was committed in this transition state

## Why We Are Pivoting
The current tree has real foundation but the implementation direction drifted:
- runtime control-plane work is useful
- UE bootstrap and bridge plumbing are useful
- current visual generator path is not the right architecture for the new goal

The next instance should not keep iterating on the existing scene grammar.

## Keep / Rewrite / Ignore

### Keep
- `workspace/dali_unreal/` project scaffold
- `workspace/dali_unreal/Config/DefaultEngine.ini`
- `workspace/dali_unreal/Source/DaliMirror/DaliMirrorBridgeSubsystem.*`
- `workspace/dali_unreal/Source/DaliMirror/DaliMirrorSettings.*`
- `workspace/cathedral/runtime.py`
- `workspace/cathedral/control_api.py`
- `scripts/dali_fishtank_start.sh`

Reason:
- these provide boot, orchestration, runtime state transport, and UE project continuity

### Rewrite
- `workspace/dali_unreal/Source/DaliMirror/DaliMirrorSceneActor.*`
- `workspace/dali_unreal/Source/DaliMirror/DaliMirrorCameraPawn.*`
- any generator assumptions that depend on live runtime semantics to invent the world every frame

Reason:
- the new plan is offline-first and intermediate-artifact-first

### Ignore For Now
- old Python/OpenGL visual semantics
- current packaged-vs-staged launcher churn
- pawn dismiss-path experiments
- incremental mesh-scatter tuning on the current UE scene actor

Reason:
- they are not the load-bearing question for the new design

## Canonical New Design Doc
Read this first:
- `workspace/dali_unreal/Docs/PhaseOneOfflinePipeline.md`

The document is the new architectural target. Treat it as the implementation contract unless the user revises it again.

## Existing Historical Context Worth Reading
- `workspace/audit/cathedral_ue5_handoff_20260308T123354Z.md`
- `memory/2026-03-08.md`
- `memory/2026-03-09.md`

These explain how the current tree got here and which lessons were already paid for.

## Recommended First Tasks For The New Instance
1. Define the offline artifact contract in code:
   - CA grid serialization format
   - archetype map format
   - prompt history format
   - landscape import format
2. Build the CA generator as a dedicated UE5 C++ plugin or module, not as scene decoration logic.
3. Create an import path in UE5 that can read the baked artifacts deterministically.
4. Leave the runtime/service path dormant until the offline pipeline has a real output chain.

## Non-Goals For The Next Pass
- do not keep tuning the current live morphogenesis scene
- do not add more symbolic overlays
- do not treat packaged-launch hygiene as the main problem
- do not commit to runtime AI before the offline pipeline is real

## Current Repo Reality
The worktree is dirty and contains a lot of prior uncommitted work outside this pivot.
Do not assume every untracked file in `workspace/` was created in this pass.
Be selective and surgical.

## Suggested Entry Command
Run:

```bash
scripts/dali_phase1_context.sh
```

Then read:
- `workspace/dali_unreal/Docs/PhaseOneOfflinePipeline.md`
- `workspace/handoffs/dali_phase1_offline_pipeline_2026-03-09.md`

## Final Note
The correct posture for the next instance is not "continue the current implementation."
It is "use the existing scaffold, but restart the generator architecture around the offline pipeline."
