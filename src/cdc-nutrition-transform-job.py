import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# Initialize Glue Context
args = getResolvedOptions(sys.argv, ['JOB_NAME'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# 1. Read from Bronze (CSV)
# Replace with your actual database/table names
datasource0 = glueContext.create_dynamic_frame.from_catalog(
    database = "cdc_nutrition_db", 
    table_name = "raw_bronze"
)

# 2. Transform: Casting and Cleaning
# Using ApplyMapping to ensure data types are correct for Parquet
transformed_df = ApplyMapping.apply(
    frame = datasource0,
    mappings = [
        ("yearstart", "string", "year", "int"),
        ("locationdesc", "string", "state", "string"),
        ("data_value", "string", "obesity_rate", "double"),
        ("question", "string", "metric_type", "string")
    ]
)

# 3. Write to Silver (Parquet)
# This format is optimized for Athena queries
glueContext.write_dynamic_frame.from_options(
    frame = transformed_df,
    connection_type = "s3",
    connection_options = {"path": "s3://cdc-nutrition-transformed-silver/refined/"},
    format = "parquet"
)

job.commit()
