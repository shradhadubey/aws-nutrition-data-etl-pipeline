import boto3
import pandas as pd
import io

s3 = boto3.client('s3')
bronze_bucket = "cdc-nutrition-raw-bronze"
silver_bucket = "cdc-nutrition-transformed-silver"

# Read CSV using Pandas (fits in memory for this dataset)
obj = s3.get_object(Bucket=bronze_bucket, Key="raw/data.csv")
df = pd.read_csv(io.BytesIO(obj['Body'].read()))

# Cleaning: lower case columns, remove nulls
df.columns = [c.lower().replace(' ', '_') for c in df.columns]
df = df.dropna(subset=['data_value'])

# Convert to Parquet and upload
buffer = io.BytesIO()
df.to_parquet(buffer, index=False)
s3.put_object(Bucket=silver_bucket, Key="refined/data.parquet", Body=buffer.getvalue())