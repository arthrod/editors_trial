# WordCraft

## What the driver runs

`build/score_all.py` measures WordCraft from `out/wordcraft`. `build/run_all.sh` runs the Rust harness under `harness/wordcraft`. This note does not publish a new round-trip percentage for that output.

## What it is

WordCraft is a Rust word processor from the ArtCraft team. The harness round-trips through that program's own reader and writer.

## Trivia

The README and `Cargo.toml` both state the license as MIT OR Apache-2.0, copyright 2026 ArtCraft Team and the WordCraft contributors. There is no file named `LICENSE` at the root. The README points at `LICENSE-MIT` and `LICENSE-APACHE`. The ArtCraft name, wordmark, and logos in `docs/brand/` are trademarks and are outside that license; forks must remove them. English hyphenation uses Grady Ward's public-domain Moby Hyphenator II word list. The project's asset rule prefers icons drawn in code, in `crates/ui-egui/src/icons.rs`. The site is getartcraft.com.
