# CDC Nutrition & Obesity Behavioral Risk Factor Pipeline

### 🚀 Project Overview
This project implements a budget-optimized, automated data engineering pipeline on AWS to process and analyze the **CDC’s Nutrition, Physical Activity, and Obesity** dataset. The architecture is designed to stay entirely within the **AWS Free Tier** and **Snowflake Free Trial** limits while maintaining professional data engineering standards.

---

###  Architecture
The pipeline follows a "Medallion Architecture" (Bronze/Silver):

1.  **Ingestion (Lambda):** A serverless Python script fetches the latest dataset from `Data.gov`.
2.  **Raw Storage (S3 Bronze):** Stores the raw CSV files with date-partitioned keys.
3.  **Discovery (Glue Crawler):** Automatically infers the schema and populates the **Glue Data Catalog**.
4.  **Transformation (Glue Python Shell):** A cost-optimized job (using Pandas) cleans the data, renames columns to SQL-friendly formats, and converts it to **Parquet**.
5.  **Refined Storage (S3 Silver):** Stores optimized Parquet files for high-performance querying.
6.  **Analytics (Athena & Snowflake):** * **Athena:** Serverless SQL for ad-hoc analysis on AWS (Always Free 1TB/mo).
    * **Snowflake:** External stage integration for cross-cloud warehousing.
7.  **Orchestration (Step Functions):** Coordinates the execution flow with error handling.



---

### 📁 Project Structure
```text

├── src/                     # Source Code
│   ├── lambda_ingest.py     # API to S3 Bronze Ingestion
│   └── glue_transform.py    # Python Shell ETL (CSV to Parquet)
├── orchestration/           # Workflow
│   └── state_machine.json   # AWS Step Functions ASL definition
└── README.md                # Project Documentation
