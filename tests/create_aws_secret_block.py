import os
from prefect_aws import AwsCredentials

aws_creds = AwsCredentials(
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
)
aws_creds.save(name="my-aws-creds", overwrite=True)