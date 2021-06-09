import json
import urllib.parse
import boto3
import os

import sys
import time

import trp


print('Loading function')

s3 = boto3.client('s3')
textract = boto3.client('textract')

def process_document(bucket, document):
    analyzer=DocumentProcessor(os.environ['SNSTopicRoleArn'], bucket,document)
    analyzer.CreateTopicandQueue()
    analyzer.ProcessDocument(ProcessType.DETECTION)
    analyzer.DeleteTopicandQueue()
    

def lambda_handler(event, context):
    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    try:
        process_document(bucket, key)

        response = s3.get_object(Bucket=bucket, Key=key)
        print("CONTENT TYPE: " + response['ContentType'])
        
        return response['ContentType']
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e



class ProcessType:
    DETECTION = 1
    ANALYSIS = 2


class DocumentProcessor:
    jobId = ''
    textract = boto3.client('textract')
    sqs = boto3.client('sqs')
    sns = boto3.client('sns')

    roleArn = ''   
    bucket = ''
    document = ''
    
    sqsQueueUrl = ''
    snsTopicArn = ''
    # snsTopicArn = os.environ['SNSTopicArn']
    processType = ProcessType.DETECTION


    def __init__(self, role, bucket, document):    
        self.roleArn = role
        self.bucket = bucket
        self.document = document    

 
    def ProcessDocument(self,type):
        jobFound = False
        
        self.processType=type
        validType=False

        #Determine which type of processing to perform
        if self.processType==ProcessType.DETECTION:
            response = self.textract.start_document_text_detection(DocumentLocation={'S3Object': {'Bucket': self.bucket, 'Name': self.document}},
                    NotificationChannel={'RoleArn': self.roleArn, 'SNSTopicArn': self.snsTopicArn})
            print('Processing type: Detection')
            validType=True        

        
        if self.processType==ProcessType.ANALYSIS:
            response = self.textract.start_document_analysis(DocumentLocation={'S3Object': {'Bucket': self.bucket, 'Name': self.document}},
                FeatureTypes=["TABLES", "FORMS"],
                NotificationChannel={'RoleArn': self.roleArn, 'SNSTopicArn': self.snsTopicArn})
            print('Processing type: Analysis')
            validType=True    

        if validType==False:
            print("Invalid processing type. Choose Detection or Analysis.")
            return

        print('Start Job Id: ' + response['JobId'])
        dotLine=0
        while jobFound == False:
            sqsResponse = self.sqs.receive_message(QueueUrl=self.sqsQueueUrl, MessageAttributeNames=['ALL'],
                                          MaxNumberOfMessages=10)

            if sqsResponse:
                
                if 'Messages' not in sqsResponse:
                    if dotLine<40:
                        print('.', end='')
                        dotLine=dotLine+1
                    else:
                        print()
                        dotLine=0    
                    sys.stdout.flush()
                    time.sleep(5)
                    continue

                for message in sqsResponse['Messages']:
                    notification = json.loads(message['Body'])
                    textMessage = json.loads(notification['Message'])
                    print(textMessage['JobId'])
                    print(textMessage['Status'])
                    if str(textMessage['JobId']) == response['JobId']:
                        print('Matching Job Found:' + textMessage['JobId'])
                        jobFound = True
                        pages = self.GetResults(textMessage['JobId'])
                        processedText = self.ProcessResults(pages)
                        self.SaveText(processedText)
                        
                        self.sqs.delete_message(QueueUrl=self.sqsQueueUrl,
                                       ReceiptHandle=message['ReceiptHandle'])
                    else:
                        print("Job didn't match:" +
                              str(textMessage['JobId']) + ' : ' + str(response['JobId']))
                    # Delete the unknown message. Consider sending to dead letter queue
                    self.sqs.delete_message(QueueUrl=self.sqsQueueUrl,
                                   ReceiptHandle=message['ReceiptHandle'])

        print('Done!')

    


    def CreateTopicandQueue(self):
      
        millis = str(int(round(time.time() * 1000)))

        #Create SNS topic
        snsTopicName="AmazonTextractTopic" + millis

        topicResponse=self.sns.create_topic(Name=snsTopicName)
        self.snsTopicArn = topicResponse['TopicArn']

        #create SQS queue
        sqsQueueName="AmazonTextractQueue" + millis
        self.sqs.create_queue(QueueName=sqsQueueName)
        self.sqsQueueUrl = self.sqs.get_queue_url(QueueName=sqsQueueName)['QueueUrl']
 
        attribs = self.sqs.get_queue_attributes(QueueUrl=self.sqsQueueUrl,
                                                    AttributeNames=['QueueArn'])['Attributes']
                                        
        sqsQueueArn = attribs['QueueArn']

        # Subscribe SQS queue to SNS topic
        self.sns.subscribe(
            TopicArn=self.snsTopicArn,
            Protocol='sqs',
            Endpoint=sqsQueueArn)

        #Authorize SNS to write SQS queue 
        policy = """{{
  "Version":"2012-10-17",
  "Statement":[
    {{
      "Sid":"MyPolicy",
      "Effect":"Allow",
      "Principal" : {{"AWS" : "*"}},
      "Action":"SQS:SendMessage",
      "Resource": "{}",
      "Condition":{{
        "ArnEquals":{{
          "aws:SourceArn": "{}"
        }}
      }}
    }}
  ]
}}""".format(sqsQueueArn, self.snsTopicArn)
 
        response = self.sqs.set_queue_attributes(
            QueueUrl = self.sqsQueueUrl,
            Attributes = {
                'Policy' : policy
            })

    def DeleteTopicandQueue(self):
        self.sqs.delete_queue(QueueUrl=self.sqsQueueUrl)
        self.sns.delete_topic(TopicArn=self.snsTopicArn)
        
    def SaveText(self, text):
        # Upload
        # upload_bucket = s3.Bucket(os.environ['DESTBUCKET'])
        upload_key = os.path.splitext(self.document)[0]+'.txt'
        upload_file = '/tmp/'+upload_key
        
        with open(upload_file, 'w') as data:
            data.write(text)
        
        # s3.upload_file(upload_file, upload_key)
        
        response = s3.upload_file(upload_file, os.environ['DESTBUCKET'], upload_key)

        

    #Display information about a block
    def DisplayBlockInfo(self,block):
        
        print ("Block Id: " + block['Id'])
        print ("Type: " + block['BlockType'])
        if 'EntityTypes' in block:
            print('EntityTypes: {}'.format(block['EntityTypes']))

        if 'Text' in block:
            print("Text: " + block['Text'])

        if block['BlockType'] != 'PAGE':
            print("Confidence: " + "{:.2f}".format(block['Confidence']) + "%")

        print('Page: {}'.format(block['Page']))

        if block['BlockType'] == 'CELL':
            print('Cell Information')
            print('\tColumn: {} '.format(block['ColumnIndex']))
            print('\tRow: {}'.format(block['RowIndex']))
            print('\tColumn span: {} '.format(block['ColumnSpan']))
            print('\tRow span: {}'.format(block['RowSpan']))

            if 'Relationships' in block:
                print('\tRelationships: {}'.format(block['Relationships']))
    
        print('Geometry')
        print('\tBounding Box: {}'.format(block['Geometry']['BoundingBox']))
        print('\tPolygon: {}'.format(block['Geometry']['Polygon']))
        
        if block['BlockType'] == 'SELECTION_ELEMENT':
            print('    Selection element detected: ', end='')
            if block['SelectionStatus'] =='SELECTED':
                print('Selected')
            else:
                print('Not selected')  

    def ProcessResults(self, pages):
        doc = trp.Document(pages)
        print("Total length of document is",len(doc.pages))
        
        # for page in doc.pages:
        #     pageText = page.text
        processedText = ' '.join([str(page.text) for page in doc.pages])
        
        print("Processed Text")
        print(processedText)
        
        return processedText

    def GetResults(self, jobId):
        maxResults = 1000
        paginationToken = None
        finished = False
        
        pages = []

        while finished == False:

            response=None

            if self.processType==ProcessType.ANALYSIS:
                if paginationToken==None:
                    response = self.textract.get_document_analysis(JobId=jobId,
                        MaxResults=maxResults)
                else: 
                    response = self.textract.get_document_analysis(JobId=jobId,
                        MaxResults=maxResults,
                        NextToken=paginationToken)                           

            if self.processType==ProcessType.DETECTION:
                if paginationToken==None:
                    response = self.textract.get_document_text_detection(JobId=jobId,
                        MaxResults=maxResults)
                else: 
                    response = self.textract.get_document_text_detection(JobId=jobId,
                        MaxResults=maxResults,
                        NextToken=paginationToken)   

            # blocks=response['Blocks'] 
            pages.append(response)
            print ('Detected Document Text')
            print ('Pages: {}'.format(response['DocumentMetadata']['Pages']))
        
            # Display block information
            # for block in blocks:
            #         self.DisplayBlockInfo(block)
            #         print()
            #         print()

            if 'NextToken' in response:
                paginationToken = response['NextToken']
            else:
                finished = True
                
        return pages

    def GetResultsDocumentAnalysis(self, jobId):
        maxResults = 1000
        paginationToken = None
        finished = False

        while finished == False:

            response=None
            if paginationToken==None:
                response = self.textract.get_document_analysis(JobId=jobId,
                                            MaxResults=maxResults)
            else: 
                response = self.textract.get_document_analysis(JobId=jobId,
                                            MaxResults=maxResults,
                                            NextToken=paginationToken)  
            

            #Get the text blocks
            blocks=response['Blocks']
            print ('Analyzed Document Text')
            print ('Pages: {}'.format(response['DocumentMetadata']['Pages']))
            # Display block information
            for block in blocks:
                    self.DisplayBlockInfo(block)
                    print()
                    print()

                    if 'NextToken' in response:
                        paginationToken = response['NextToken']
                    else:
                        finished = True