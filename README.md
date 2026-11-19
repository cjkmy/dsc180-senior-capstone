# From Policy to Performance: Exploring Generative AI in Higher Education

## Project Overview

This project investigates how Generative AI (GenAI) policies have evolved and how those policies may relate to student academic performance. The team will examine differences in how instructors regulate AI use and explore patterns across UC San Diego course grades.

This repository currently contains exploratory grade data and a notebook for inspecting it. Syllabus collection and classification code are planned but are not yet included.

## Repository Contents

- `data/ucsd_grades.csv` — a subset of UCSD grade-distribution records.
- `data/ucsd_all_grades.csv` — the larger UCSD grade-distribution data file.
- `data-processing.ipynb` — a Jupyter notebook that loads the larger grades file and lists the unique values in selected columns.
- `README.md` — setup and reproducibility instructions.

## Data

The CSV files are committed to this GitHub repository, so no separate download is required. Clone the repository and keep the files in the `data/` directory to match the notebook's relative file paths.

Each CSV includes course and instructor fields, such as `Subject`, `Course`, `Year`, `Quarter`, `Title`, and `Instructor`, as well as `GPA` and grade-distribution fields. The files contain 171 and 30,146 data rows respectively, excluding their headers.

### Obtaining the data

If the repository is already cloned, the data is available under `data/`. To obtain a fresh copy from GitHub:

```bash
git clone https://github.com/cjkmy/dsc180-senior-capstone.git
cd dsc180-senior-capstone
```

Do not rename or move the CSV files unless you update the corresponding paths in the notebook. The data can be regenerated or replaced by another script only if that script documents its source and writes the resulting file to `data/ucsd_all_grades.csv` or `data/ucsd_grades.csv`.

## Software Requirements

- Git
- Python 3.10 or newer
- Jupyter Notebook or JupyterLab
- pandas

An isolated virtual environment is recommended.

## Environment Setup

From the repository root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pandas jupyter
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Reproducing the Current Analysis

With the virtual environment active, start Jupyter from the repository root:

```bash
jupyter notebook
```

Then open `data-processing.ipynb` and run all cells in order. The first code cell imports pandas, and the second loads `data/ucsd_all_grades.csv` and prints all unique values for:

- `Subject`
- `Course`
- `Year`
- `Quarter`
- `Title`
- `Instructor`
- `GPA`

You can also execute the notebook from the command line:

```bash
jupyter nbconvert --execute --inplace data-processing.ipynb
```

The notebook should be run from the repository root because it uses the relative path `data/ucsd_all_grades.csv`.

## Verifying the Setup

Run:

```bash
python -c "import pandas as pd; print(pd.__version__)"
python -c "import pandas as pd; df = pd.read_csv('data/ucsd_all_grades.csv'); print(df.shape)"
```

A successful setup will print the installed pandas version and a two-dimensional table size in the format `(rows, columns)`.

## Future Reproducibility

The following artifacts should be added as the project progresses:

- A pinned dependency file such as `requirements.txt` or `environment.yml`.
- Scripts or notebooks for syllabus acquisition and preprocessing.
- A documented classification methodology and model configuration.
- Commands that produce cleaned datasets and final figures or tables.
- Random seeds and any model/checkpoint information needed to reproduce results.

No external syllabus or model data should be required to run the current grade-data notebook.
