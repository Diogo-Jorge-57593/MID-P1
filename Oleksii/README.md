# DMI Project P1: Venture Capital Data Sources (Subtopic 1)

## Project Structure
* `data/` - Contains the raw scraped CSV files and the generated JSON KPI metrics (`json_metrics/` directory).
* `database/` - Contains `init_db.sql` to build and populate the PostgreSQL database.
* `src/` - Python scripts used for LLM data extraction and synthetic JSON generation.
* `queries/` - Local SQL queries for Subtopic 1.
* `models/` - Database diagrams and schemas.

## Setup & Execution Instructions

### 1. Relational Database (PostgreSQL)
1. Open DBeaver (or any PostgreSQL client) and connect to your local PostgreSQL server.
2. Create a new database named `dmi_investments`.
3. Open the `database/init_db.sql` file in the SQL editor.
4. Execute the entire script to create the tables (`investors`, `startups`, `funding_rounds`) and populate them with the extracted data.
5. The local queries can be executed directly against this database using the files in the `queries/` folder.

### 2. Semi-Structured Document Store (JSON)
1. No database engine is required for this source.
2. The JSON files are located in `data/json_metrics/`. Each file contains the monthly financial KPIs (MRR, CAC, Churn) mapped to the `startup_id` from the PostgreSQL database.