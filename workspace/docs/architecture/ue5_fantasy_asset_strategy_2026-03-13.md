# UE5 Fantasy Asset Strategy - 2026-03-13

## Problem

The first `fantasy_landscape` pass proved the UE5 lane could boot and draw a scene, but it is not a sustainable content strategy.

The failure mode was structural:

- almost no authored content exists in `workspace/dali_unreal/Content`
- scene composition lived in one large C++ function
- engine primitives (`Sphere`, `Cube`, `Cylinder`, `Cone`) were being used as the de facto asset library
- one preview-material family was being stretched across sky, terrain, props, creatures, water, and effects

That is acceptable for a preview. It is the wrong base for a scene that needs to become charming, readable, and repeatedly polishable.

## Direction

The new target is `fantasy_landscape_v2`.

`v2` is not yet a full authored-art pipeline, but it deliberately moves toward a 2.5D scene grammar:

- layered thin-card silhouettes instead of volumetric cube sculpture
- clearer separation of scene roles:
  - `SkyInstances`
  - `MembraneInstances` for deep ridges
  - `HabitatInstances` for nearer terrain/foliage
  - `AccentInstances` for props/house/meadow
  - `OrganInstances` for creatures and high-contrast moving forms
  - `WaterInstances` for pond surface
  - `SeedInstances` for glow accents, moon, fire, artifact, splashes
- camera/framing tuned for a flatter storybook read

## Principle

Use UE5 as the runtime and renderer, not as an excuse to hand-place every visual element in C++ forever.

The right long-term stack is:

1. scene data
2. small authored silhouette/prop kits
3. material families per layer
4. Niagara for motion/effects
5. runtime orchestration in C++

Not:

1. giant monolithic function
2. more cubes
3. more manual transforms

## Immediate Next Steps

1. Promote `fantasy_landscape_v2` to use external scene data instead of hard-coded transforms.
2. Add a real silhouette kit for:
   - house body / roof / porch
   - duck poses
   - dragon poses
   - tree canopies
   - cave mouth / shoreline / reeds
3. Move smoke, fire breath, fireflies, and splashes into Niagara.
4. Split materials into distinct authored families instead of parameter-tinting one preview material.
5. Resolve live runtime promotion separately from content work; current runtime instability is GPU/windowing related, not scene-compilation related.
