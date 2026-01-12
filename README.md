# CDC Nutrition & Obesity Behavioral Risk Factor Pipeline

## 🚀 Project Overview
This project implements a budget-optimized, automated data engineering pipeline on AWS to process and analyze the **CDC’s Nutrition, Physical Activity, and Obesity** dataset. The architecture is designed to stay entirely within the **AWS Free Tier** and **Snowflake Free Trial** limits while maintaining professional data engineering standards.

---

##  Architecture
The pipeline follows a "Medallion Architecture" (Bronze/Silver):

1.  **Ingestion (Lambda):** A serverless Python script fetches the latest dataset from `Data.gov`.
2.  **Raw Storage (S3 Bronze):** Stores the raw CSV files with date-partitioned keys.
3.  **Discovery (Glue Crawler):** Automatically infers the schema and populates the **Glue Data Catalog**.
4.  **Transformation (Glue Python Shell):** A cost-optimized job (using Pandas) cleans the data, renames columns to SQL-friendly formats, and converts it to **Parquet**.
5.  **Refined Storage (S3 Silver):** Stores optimized Parquet files for high-performance querying.
6.  **Analytics (Athena & Snowflake):** * **Athena:** Serverless SQL for ad-hoc analysis on AWS (Always Free 1TB/mo).
    * **Snowflake:** External stage integration for cross-cloud warehousing.
7.  **Orchestration (Step Functions):** Coordinates the execution of Lambda, Glue Jobs, and Crawlers.


---

## Project Structure
```text

├── src/                     # Source Code
│   ├── lambda_ingest.py     # API to S3 Bronze Ingestion
│   └── glue_transform.py    # Python Shell ETL (CSV to Parquet)
├── orchestration/           # Workflow
│   └── state_machine.json   # AWS Step Functions ASL definition
└── README.md                # Project Documentation
```
## Challenges & Solutions

#### 1. The "Invisible Script" Error (S3 NoSuchKey)
Challenge: The Glue Job failed immediately, claiming the script file didn't exist in S3, even though it was visible in the console.

Root Cause: A mismatch between the "Job Name" and the actual file path in the aws-glue-assets bucket, often caused by renaming the job in the console.

Solution: Manually updated the Script Path in the Glue Job details to point to the exact S3 URI and ensured the Glue-Role had s3:GetObject permissions for the asset bucket.

#### 2. IAM vs. Lake Formation "Gatekeeping"
Challenge: Even with AdministratorAccess, Athena returned TABLE_NOT_FOUND or "Access Denied" when trying to query the Glue table.

Root Cause: AWS Lake Formation was enabled by default, acting as a secondary security layer that overrides IAM.

Solution: Granting Super permissions to the IAMAllowedPrincipals group within the Lake Formation console. This "bridged" the gap, allowing standard IAM policies to manage data access.

#### 3. The "Empty Table" Crawler Bug
Challenge: The Crawler ran successfully but created a table with zero columns (no schema).

Root Cause: The Crawler's Schema Change Policy was set to LOG mode, which prevents it from actually modifying the Data Catalog.

Solution: Updated the Crawler configuration's "Advanced Options" to "Update the table definition in the data catalog".
