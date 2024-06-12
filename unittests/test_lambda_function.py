from aws_cdk import App
from pipeline.lambda_stack import LambdaStack
from moto import mock_aws
import handler
import boto3
import os

def test_lambda_stack():

    # GIVEN
    app = App()

    # WHEN
    LambdaStack(app, 'Stack', 'UnitTestTag')

    # THEN
    template = app.synth().get_stack_by_name('Stack').template
    functions = [resource for resource in template['Resources'].values()
                if resource['Type'] == 'AWS::Lambda::Function']

    assert len(functions) == 1
    assert functions[0]['Properties']['MemorySize'] == 1024
    assert functions[0]['Properties']['PackageType'] == 'Image'
    assert functions[0]['Properties']['Timeout'] == 30

@mock_aws
def test_lambda_handler():
    os.environ['AWS_DEFAULT_REGION'] = 'us-west-2'
    s3 = boto3.client("s3")
    # GIVEN
    # Create a mock S3 bucket
    bucket_name = "test-bucket"
    s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': 'us-west-2'})

    # Create a mock S3 object
    object_key = "path/to/object.txt"
    object_content = "This is a test object."
    s3.put_object(Bucket=bucket_name, Key=object_key, Body=object_content)

    event = {
        'Records': [
            {
                's3': {
                    'bucket': {
                        'name': "test-bucket"
                    },
                    'object': {
                        'key': "path/to/object.txt"
                    }
                }
            }
        ]

    }
    context = {}

    # WHEN
    response = handler.handler(event, context)

    # THEN
    assert response == "This is a test object."