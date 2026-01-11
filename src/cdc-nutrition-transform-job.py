import sys
import boto3
import pandas as pd
import io
from awsglue.utils import getResolvedOptions

# Initialize S3 client
s3 = boto3.client('s3')

# Define your bucket names (update these if yours are different)
BRONZE_BUCKET = "cdc-nutrition-raw-bronze"
SILVER_BUCKET = "cdc-nutrition-transformed-silver"
INPUT_KEY = "raw/Nutrition__Physical_Activity__and_Obesity_-_Behavioral_Risk_Factor_Surveillance_System.csv"
OUTPUT_KEY = "refined/cdc_nutrition_data.parquet"

def transform_data():
    print(f"Reading file from: s3://{BRONZE_BUCKET}/{INPUT_KEY}")
    
    # 1. Get the CSV file from Bronze
    response = s3.get_object(Bucket=BRONZE_BUCKET, Key=INPUT_KEY)
    csv_content = response['Body'].read()
    
    # 2. Load into Pandas (optimized for Python Shell memory)
    df = pd.read_csv(io.BytesIO(csv_content))
    
    # 3. Clean: Lowercase columns, replace spaces with underscores
    df.columns = [c.lower().replace(' ', '_').replace('(', '').replace(')', '') for c in df.columns]
    
    # 4. Filter: Remove rows where the main data value is missing
    if 'data_value' in df.columns:
        df = df.dropna(subset=['data_value'])
    
    # 5. Convert to Parquet in-memory
    # Python Shell has 'awswrangler' or 'pandas' pre-installed for this
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
    
    # 6. Upload to Silver bucket
    print(f"Uploading cleaned Parquet to: s3://{SILVER_BUCKET}/{OUTPUT_KEY}")
    s3.put_object(
        Bucket=SILVER_BUCKET, 
        Key=OUTPUT_KEY, 
        Body=parquet_buffer.getvalue()
    )
    
    print("Transformation complete!")

if __name__ == "__main__":
    transform_data()