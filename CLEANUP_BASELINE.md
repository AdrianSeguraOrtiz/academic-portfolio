# Cleanup Baseline

Baseline created on `2026-05-07T21:44:38+02:00`.

This baseline corresponds to the current working tree state at the start of the
cleanup roadmap. The repository already contained uncommitted changes from the
portfolio and website work, so this baseline records that state rather than a
clean `HEAD`.

## Command Results

| Command | Result |
| --- | --- |
| `make validate-data` | Passed: 21 YAML files, 116 IDs |
| `make test` | Passed: 17 tests |
| `make lint` | Passed |
| `make site` | Passed: generated `build/site/index.html` |
| `make cv` | Passed: generated `build/cv/academic_full.md` |
| `node --check assets/site/dissemination.js` | Passed |
| `node --check assets/site/career-timeline.js` | Passed |
| `node --check assets/site/collaborations.js` | Passed |
| `git diff --check` | Passed |
| `rg -n "undefined|null|None" build/site/index.html build/cv/academic_full.md` | No matches |

## Generated Artifact Checksums

```text
4de07a2e6aa6a1c0a596a04c9965b72084a6c24237a3a046bffe1cce73dbbd99  build/site/index.html
cd4b265134e408901aabc55a9a3c94227b4c1e6826aaa1490ea2625bff5a97fa  build/site/assets/site.css
e0eb86dfbc72667567e57c7ae5f35a1f2f76d9e50b4aa69808c75549faa8462f  build/site/assets/career-timeline.js
42689ecc0463703f11e590503524b250b33c303300224f07dc099ff798dd6ed1  build/site/assets/collaborations.js
d167ae01a20ec59cf94341a30d5505666aef6956da058f6e7f728ab40d8cde2a  build/site/assets/dissemination.js
5bf3717a7c00db5e381116d473e7ac0f8a7be1efbb27da741a7bcc94d86eb9cb  build/cv/academic_full.md
```

## Visual References

Firefox headless screenshots were generated at `1440x1200`.

| Section | File | SHA-256 |
| --- | --- | --- |
| Home | `build/baseline/phase0/home.png` | `26063ad8fe10cc6da527d9bec7614b5dc73d4a3da2c79f6ad5463f8a5146a109` |
| Software | `build/baseline/phase0/software.png` | `37c8e4024c7ab4c6a88c4cca83c9ba2cd6b5ec6320150cc0e410ded5509f7cc0` |
| Career | `build/baseline/phase0/career.png` | `e9e88f683dedbca6651965f6068206c456760d1ebe8cb856165626c1efe6d5a9` |
| Organizations | `build/baseline/phase0/organizations.png` | `2dd88f2091529357e3cbbd28c90f07f708c1b69c50a98ae623bcf6f7df2ced25` |

Firefox emitted non-fatal headless warnings about X server access and Glean
initialization. The screenshots were created successfully.

## Current Worktree Note

At baseline time, `git status --short` included existing modified and untracked
files from the current portfolio work. This is expected for this cleanup pass.
Future cleanup commits should be grouped logically as described in
`CLEANUP_ROADMAP.md`.
