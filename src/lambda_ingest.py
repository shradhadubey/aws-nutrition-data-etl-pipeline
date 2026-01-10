import boto3
import urllib3
import os

def lambda_handler(event, context):
    http = urllib3.PoolManager()
    url = "https://data.cdc.gov/api/views/hn4x-zwk7/rows.csv?accessType=DOWNLOAD"
    bucket = "cdc-nutrition-raw-bronze" 
    
    # Efficient streaming to S3
    response = http.request('GET', url)
    s3 = boto3.client('s3')
    s3.put_object(Bucket=bucket, Key="raw/data.csv", Body=response.data)
    
    return {"status": "success"}