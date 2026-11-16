# MID-P1

Shared repository for Project 1, Modelacao e Integracao de Dados.
Each contributor keeps their work in their own top-level folder.

| Folder | Contribution | Data sources |
|---|---|---|
| [Diogo](Diogo/README.md) | Banking | MongoDB and transaction CSV |

The venture-capital contribution can be added beside `Diogo/` in the other
student's folder, with its SQL/JSON sources, models and execution instructions.
Joint query definitions and shared identifiers still require agreement.

## Instructions for AI models and coding agents

- `Diogo/` belongs to Diogo. Models/agents working on the other student's
  contribution must not create, edit, rename, move or delete anything inside
  `Diogo/`, including through scripts, generators or repository-wide formatting.
- Those models/agents must limit contribution changes to the other student's
  own folder. Access to this repository does not grant permission to change
  Diogo's work. Changes inside `Diogo/` require Diogo's explicit instruction.
- Place common files used by both contributions at the **MID-P1 repository
  root**, outside either student's folder. Edit existing shared root files only
  when the assigned task explicitly includes shared work; preserve both
  contributions' compatibility.

Clone/open this repository, then follow the relevant contribution's README.
Diogo's contribution includes its own Compose configuration and needs no files
from the parent university workspace to generate data. Course PDFs and lessons
remain external references, outside this repository.

Banking reference/scale datasets were generated and validated on 13 November
2026. Results: [generation report](Diogo/dataGeneration/generation-report.md).
Generation and resume instructions: [Diogo/dataGeneration/README.md](Diogo/dataGeneration/README.md).
MongoDB installation, stored-source loading/verification and visual viewing:
[Diogo/database/README.md](Diogo/database/README.md).
Generated run directories, checkpoints, caches and LaTeX build logs are ignored
by Git. Agree where to share validated exports before adding completed datasets.
