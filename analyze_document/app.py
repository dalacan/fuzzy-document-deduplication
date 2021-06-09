import json
import urllib.parse
import boto3
import os

# from bson import json_util


print('Loading function')

s3 = boto3.client('s3')
comprehend = boto3.client('comprehend')

def analyze_documents():
    input_s3_url = "s3://"+os.environ['INPUTBUCKET']
    input_doc_format = "ONE_DOC_PER_FILE"
    output_s3_url = "s3://"+os.environ['OUTPUTBUCKET']
    data_access_role_arn = os.environ['ComprehendRoleArn']
    number_of_topics = 20
     
    input_data_config = {"S3Uri": input_s3_url, "InputFormat": input_doc_format}
    output_data_config = {"S3Uri": output_s3_url}
     
    start_topics_detection_job_result = comprehend.start_topics_detection_job(NumberOfTopics=number_of_topics,
                                                                                  InputDataConfig=input_data_config,
                                                                                  OutputDataConfig=output_data_config,
                                                                                  DataAccessRoleArn=data_access_role_arn)
     
    print('start_topics_detection_job_result: ')
    print(start_topics_detection_job_result)
     
    job_id = start_topics_detection_job_result["JobId"]
     
    print('job_id: ' + job_id)
     
    describe_topics_detection_job_result = comprehend.describe_topics_detection_job(JobId=job_id)
     
    print('describe_topics_detection_job_result: ')
    print(describe_topics_detection_job_result)
     
    list_topics_detection_jobs_result = comprehend.list_topics_detection_jobs()
     
    print('list_topics_detection_jobs_result: ')
    print(list_topics_detection_jobs_result)

    

def lambda_handler(event, context):
    # Get the object from the event and show its content type
    try:
        analyze_documents()
        return 1
    except Exception as e:
        print(e)
        
        raise e



