# Fire Embodied Carbon App — Folder Guide

This document explains how the app's folder is organised, so that
when it's shared as a zipped package, it's clear what each part does
and where to look for what you need. It's meant as an orientation
guide rather than a technical manual — for methodology and detailed
usage instructions, see the **Help** page inside the running app.

## Top-level files

- **`Home.py`** — the app's entry point. This is the file that gets
  run to launch the app; you shouldn't need to open it directly.
- **`requirements.txt`** — the list of software packages the app
  depends on, used to set up the environment it runs in.

## `pages/` — the app's screens

Each file here is one screen of the app, in the order they appear in
the sidebar:

- **Fire Design** — the main assessment workflow: project setup,
  system identification, compliance pathway, quantities, and
  emission-factor matching.
- **Compare Results** — side-by-side comparison of two saved
  assessment versions.
- **Help** — methodology notes, version management, and database
  management tools.

## `components/`

Reusable pieces of the interface (tables, charts, form sections) that
get shared across the different screens above, rather than being
built from scratch each time.

## `utils/`

The app's internal engine — calculations, report generation,
standards lookups, and database reading/writing logic. This folder is
what actually powers everything the screens display. It's not meant
to be opened or edited directly.

## `database/` — the editable engineering databases

This is the folder most relevant to keeping the app's data current.
It contains three workbooks, split across two subfolders:

- **`databases/`** — the live files the app reads from at runtime:
  - `EC_Database.xlsx` — apparatus-level embodied carbon factors.
  - `Building_Class.xlsx` — NCC building classes and which standards
    apply to each.
  - `Standards_Calc_Database_Finalised.xlsx` — drives the on-screen
    questions and the standards-based quantity calculations.
- **`defaults/`** — permanent factory-default copies of the same
  three files, kept as a safety net. If a live file is edited or
  replaced and something goes wrong, the Help page's "Revert to
  Default" option restores from here.

These files can be downloaded, edited, and re-uploaded from the Help
page's **Manage Database** section — uploads are checked against the
required structure before being accepted, so a malformed file can't
break the app.

## `data/`

Holds `project_store.db`, where saved projects and assessment
versions are stored locally. This is what lets you return to a
project later or compare versions.

## `assets/`

Logos and images used throughout the app's interface.

---

For questions on methodology, the databases, or the codebase, 
please do not hesitate to reach out to the JFC team directly.