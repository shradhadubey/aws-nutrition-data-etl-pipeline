print("!! LAMBDA IS STARTING !!")

import json
import boto3
import urllib3
import datetime

s3 = boto3.client('s3')

def lambda_handler(event, context):
    # API Configuration
    # Using .csv endpoint is better for Glue/Athena tabular data
    print("!! HANDLER TRIGGERED !!")
    API_URL = "https://data.cdc.gov/resource/hn4x-zwk7.csv"
    BUCKET_NAME = "cdc-nutrition-raw-bronze"
    
    # Generate unique filename for the Bronze layer
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    FILE_NAME = f"cdc_nutrition_{timestamp}.csv"
    
    http = urllib3.PoolManager()
    
    try:
        print(f"Requesting data from: {API_URL}")
        
        # Optional: If you sign up for a Socrata App Token, add it here:
        # headers = {'X-App-Token': 'YOUR_TOKEN_HERE'}
        response = http.request('GET', API_URL, timeout=30.0)
        
        if response.status != 200:
            raise Exception(f"API Error: Status {response.status}")

        # Upload the raw CSV data to S3
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"raw/{FILE_NAME}",
            Body=response.data,
            ContentType='text/csv'
        )
        
        s3_path = f"s3://{BUCKET_NAME}/raw/{FILE_NAME}"
        print(f"Success! Data saved to: {s3_path}")

        # This return structure is essential for Step Functions to pass data to Glue
        return {
            'statusCode': 200,
            'execution_date': timestamp,
            's3_path': s3_path,
            'file_name': FILE_NAME
        }

    except Exception as e:
        print(f"Execution Failed: {str(e)}")
        raise e