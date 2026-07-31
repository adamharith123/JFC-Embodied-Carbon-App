# Fire Embodied Carbon App (FECA)

Developed by Jacaranda Flame Consulting (JFC), in collaboration with ARUP.
Status: **Release Candidate**.

Estimates the **upfront embodied carbon (A1–A5)** of fire safety systems
in buildings — from project setup through to a PDF report.

## What it does

1. **Project & Building Setup** — project details and NCC building class.
2. **System Identification** — ten fire safety categories (Detection,
   Warning, Egress, First Aid Fire-Fighting, Structural Fire Protection,
   Suppression, Smoke Hazard Management, Fire Brigade Access, Fire
   Safety Management, Special Hazards).
3. **Compliance Pathway** — each system marked Not Applicable,
   Deemed-to-Satisfy (DtS), or Manual Override.
4. **Quantity Determination** — from user input, standards-based rules
   (e.g. detector/sprinkler spacing), or system-specific calculators.
5. **Product & Emission Factor Matching** — matched to manufacturer
   EPDs where available, Australian industry-average data otherwise,
   or mass-based estimates as a last resort.
6. **Calculation & Reporting** — carbon by lifecycle stage (A1–A3, A4,
   A5), shown via tables/charts and exportable as a PDF. Assessments
   save as versions for comparing design iterations.

Scope is upfront embodied carbon only — no operational or
end-of-life stages. The full methodology, workflow and references are
also built into the app's **Help** page.

### Pages
| Page | Purpose |
|---|---|
| Home | Landing page, launches a new assessment |
| Fire Design | The main assessment workflow (steps 1–6 above) |
| Compare Results | Side-by-side comparison of two saved versions |
| Help | Methodology, version management, database management |

## Running the app

Requires Python 3.11 via Conda, with packages from `requirements.txt`
(Streamlit, pandas, openpyxl, plotly, xlsxwriter, reportlab, kaleido,
qrcode).

- **macOS:** double-click `run_app.command` — sets up/activates the
  `JFC-Embodied-Carbon-App` Conda environment, syncs dependencies, and
  launches at `http://localhost:8501` (also reachable from other
  devices on the same Wi-Fi via the QR code on the Home page). Stop
  with `stop_app.command`.
- **Windows:** double-click `run_app.bat` / `stop_app.bat` (same
  behaviour).
- **Manual, once the environment exists:**
  ```bash
  streamlit run Home.py --server.address=0.0.0.0 --server.port=8501
  ```

## Folder structure

```
Home.py            Entry point
pages/              Fire Design, Compare Results, Help
components/         Reusable UI building blocks
utils/              Calculations, database loading, report generation,
                    standards lookups, session state
database/
  databases/          Live databases the app reads at runtime
  defaults/           Factory-default copies, for "Revert to Default"
data/
  project_store.db    Saved projects/versions (SQLite)
assets/             Logos
```

## The engineering databases

Read at runtime from `database/databases/`:

| File | Role |
|---|---|
| `ARUP_v2_Finalised.xlsx` | Carbon Database — apparatus-level embodied carbon factors |
| `standards_database_master.xlsx` | Building Class Database — NCC building classes and applicable standards |
| `Standards_Calc_Database_Finalised.xlsx` | UI & Calculation Database — drives the on-screen questions and standards-based calculations |

Manage these from the Help page → **Manage Database**: download the
current copy to edit offline, upload a replacement (validated against
required sheets/columns before it's accepted), or revert to the
factory default at any time.

## Known limitations

- **Local, single-user tool** — runs per machine, not a hosted
  multi-user web app. Project data lives in the local
  `data/project_store.db` and isn't centrally backed up or shared
  between machines.
- **Data quality hierarchy** — emission factors fall back from
  manufacturer EPD → industry-average → mass-based estimate depending
  on what's available for a given product; worth keeping in mind when
  reviewing results.

## Source control

Version-controlled on GitHub
(`adamharith123/JFC-Embodied-Carbon-App`). Happy to arrange access or
a repository transfer as part of handover.

## Contact

For questions on methodology, the databases, or the codebase, please
reach out to the JFC team directly.