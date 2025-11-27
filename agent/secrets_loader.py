import os
import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def load_secrets(secret_name: str, region_name: str = "us-west-2"):
    """
    Load configuration from AWS Secrets Manager into environment variables.

    Args:
        secret_name: The name of the secret to retrieve (required).
        region_name: AWS region where the secret is stored.
    """
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    # Try to find the secret if the exact name isn't known (optional robust look-up)
    # For now, we assume the name passed is correct or we rely on the CDK output naming convention
    
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # If secret not found or permission denied, log warning and return
        logger.warning(f"Could not retrieve secret '{secret_name}': {e}")
        return

    if 'SecretString' in get_secret_value_response:
        secret = get_secret_value_response['SecretString']
        try:
            secret_dict = json.loads(secret)
            for key, value in secret_dict.items():
                if key not in os.environ:
                    os.environ[key] = str(value)
                    logger.info(f"Loaded config: {key}")
        except json.JSONDecodeError:
            logger.error("Secret is not valid JSON")
    else:
        logger.warning("Secret content is binary, skipping load.")

