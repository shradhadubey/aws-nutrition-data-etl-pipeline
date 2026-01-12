# CDC Nutrition & Obesity Behavioral Risk Factor Pipeline

## 🚀 Project Overview
This project implements a budget-optimized, automated data engineering pipeline on AWS to process and analyze the **CDC’s Nutrition, Physical Activity, and Obesity** dataset. An automated, serverless data pipeline that ingests CDC nutrition data, transforms it from CSV to Parquet, and catalogs it for high-performance SQL analytics using AWS.  The architecture is designed to stay entirely within the **AWS Free Tier** and **Snowflake Free Trial** limits while maintaining professional data engineering standards.


---

##  Architecture Overview
This project implements a **Medallion Data Lake** architecture to refine raw data into analytics-ready assets:

1.  **Ingestion (Lambda):** A serverless Python script fetches the latest dataset from `Data.gov`.
2.  **Raw Storage (S3 Bronze):** Stores the raw CSV files with date-partitioned keys.
3.  **Discovery (Glue Crawler):** Automatically infers the schema and populates the **Glue Data Catalog**.
4.  **Transformation (Glue Python Shell):** A cost-optimized job (using Pandas) cleans the data, renames columns to SQL-friendly formats, and converts it to **Parquet**.
5.  **Refined Storage (S3 Silver):** Stores optimized Parquet files for high-performance querying.
6.  **Analytics (Athena & Snowflake):** * **Athena:** Serverless SQL for ad-hoc analysis on AWS (Always Free 1TB/mo).
    * **Snowflake:** External stage integration for cross-cloud warehousing.
7.  **Orchestration (Step Functions):** Coordinates the execution of Lambda, Glue Jobs, and Crawlers.

---

## Manual Setup Instructions

This pipeline was built manually to ensure a deep understanding of service interactions before moving to Infrastructure-as-Code (IaC).

### 1. S3 Storage Setup
Create two S3 buckets in your region (e.g., `ap-southeast-2`):
* `cdc-nutrition-raw-bronze`: For raw CSV ingestion.
* `cdc-nutrition-transformed-silver`: For refined Parquet data.

### 2. IAM Role Configuration
Create an IAM Role named `CDC-Glue-Role` with **Glue** as the trusted entity. Attach the following:
* **Policy:** `AWSGlueServiceRole` (Managed).
* **Inline Policy:** Add permissions for `s3:GetObject`, `s3:PutObject`, and `glue:CreateTable` specifically for your buckets and the `cdc_nutrition_db` database.

### 3. Glue Data Catalog & Crawler
1.  **Database:** Create `cdc_nutrition_db` in Glue.
2.  **Crawler:** Create `cdc-nutrition-silver-crawler`.
    * **Source:** `s3://cdc-nutrition-transformed-silver/refined/`
    * **Output Behavior:** Set "Update the table definition" to ensure the schema is written (avoiding `LOG` mode issues).

### 4. Glue ETL Job
1.  **Job Type:** Spark (PySpark).
2.  **Script:** Use the script provided in `/glue/transform_job.py`.
3.  **Details:** Link the `CDC-Glue-Role` and set the script path to your S3 assets folder.

---

## ✅ Verification Checklist

- [ ] **Lambda:** Check `bronze` bucket for new `.csv` file.
- [ ] **Glue Job:** Verify `Succeeded` status and check `silver` bucket for `.parquet` files.
- [ ] **Crawler:** Verify "1 table change" in the run summary.
- [ ] **Glue Table:** Confirm the `refined` table schema is populated with columns.
- [ ] **Athena:** Run `SELECT * FROM cdc_nutrition_db.refined LIMIT 10;` and confirm data displays.

---
## Challenges & Solutions

#### 1. The "Invisible Script" Error (S3 NoSuchKey)
* **Challenge:**  The Glue Job failed immediately, claiming the script file didn't exist in S3, even though it was visible in the console.

* **Root Cause:** A mismatch between the "Job Name" and the actual file path in the aws-glue-assets bucket, often caused by renaming the job in the console.

* **Solution:** Manually updated the Script Path in the Glue Job details to point to the exact S3 URI and ensured the Glue-Role had s3:GetObject permissions for the asset bucket.

#### 2. IAM vs. Lake Formation "Gatekeeping"
* **Challenge:** Even with AdministratorAccess, Athena returned TABLE_NOT_FOUND or "Access Denied" when trying to query the Glue table.

* **Root Cause:** AWS Lake Formation was enabled by default, acting as a secondary security layer that overrides IAM.

* **Solution:**  Granting Super permissions to the IAMAllowedPrincipals group within the Lake Formation console. This "bridged" the gap, allowing standard IAM policies to manage data access.

#### 3. The "Empty Table" Crawler Bug
* **Challenge:**  The Crawler ran successfully but created a table with zero columns (no schema).

* **Root Cause:** The Crawler's Schema Change Policy was set to LOG mode, which prevents it from actually modifying the Data Catalog.

* **Solution:**  Updated the Crawler configuration's "Advanced Options" to "Update the table definition in the data catalog".
---

## Project Structure
* `/lambda`: CDC API ingestion script.
* `/glue`: PySpark transformation script.
* `/iam`: JSON policy definitions.
* `/step_functions`: ASL definition for orchestration.

```text

├── src/                     # Source Code
│   ├── lambda_ingest.py     # API to S3 Bronze Ingestion
│   └── glue_transform.py    # Python Shell ETL (CSV to Parquet)
├── orchestration/           # Workflow
│   └── state_machine.json   # AWS Step Functions ASL definition
└── README.md                # Project Documentation
```
