# Build Target Policy

Three-tier verification ladder — use the lightest tool that answers the question:

| Tier | Tool | When | Speed |
|------|------|------|-------|
| Per-edit | `lean_diagnostic_messages(file)` | After every edit | Sub-second |
| File compile | `lake env lean <path/to/File.lean>` | File-level gate, import checks | Seconds |
| Project gate | `lake build` | Checkpoint, final gate, `/lean4:checkpoint` | Minutes |

Run `lake env lean` from the Lean project root; pass repo-relative file paths.

**Never use `lake build <file basename>`** — `lake build` does not accept file path arguments. Use `lake env lean <path/to/File.lean>` for single-file compilation.
