# Node Naming Migration

Legacy Node Name Notice: This document intentionally references `System-1` and `System-2` during the compatibility window.

## Canonical Names

- `dali` is the canonical node ID for legacy `System-1`.
- `c_lawd` is the canonical node ID for legacy `System-2`.

## Alias Policy (One Compatibility Cycle)

Accepted aliases are defined in `workspace/policy/system_map.json`:

- `system1`, `system-1` -> `dali`
- `system2`, `system-2` -> `c_lawd`

New code should use canonical IDs. Legacy names remain valid only through the migration window.

## Identity and Memory Separation

- `nodes/dali/IDENTITY.md`
- `nodes/dali/MEMORY.md`
- `nodes/c_lawd/IDENTITY.md`
- `nodes/c_lawd/MEMORY.md`

Legacy docs are not removed immediately; they remain as compatibility references with pointers.
