# Checkpoint Logic

If `--commit=never`, skip the checkpoint commit entirely — changes remain in the working tree.

Otherwise, if `--checkpoint` is enabled and there is a non-empty diff:
- **prove:** Stage only files from **accepted** fills (exclude declined fills)
- **autoprove:** Stage only files from successful, non-rolled-back work
- **Both:** Exclude files from rolled-back deep invocations — those files are restored to pre-deep state and must not be staged
- Commit: `git commit -m "checkpoint(lean4): [summary]"`

If no files changed during this cycle, emit:
> No changes this cycle — skipping checkpoint

Do NOT create an empty commit. Checkpoint requires a non-empty diff.
