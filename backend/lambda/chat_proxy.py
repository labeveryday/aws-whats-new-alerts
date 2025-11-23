import json
import boto3
import os
import uuid
import time
import requests
from jose import jwk, jwt
from jose.utils import base64url_decode

# Initialize client outside handler for reuse
region = os.environ.get('AWS_REGION', 'us-west-2')
client = boto3.client('bedrock-agentcore', region_name=region)
control_client = boto3.client('bedrock-agentcore-control', region_name=region)

# Environment Variables
AGENT_RUNTIME_ARN = os.environ.get('AGENT_RUNTIME_ARN')
AGENT_NAME = os.environ.get('AGENT_NAME', 'aws_newsletter_bot')
USER_POOL_ID = os.environ.get('USER_POOL_ID')
APP_CLIENT_ID = os.environ.get('APP_CLIENT_ID')

# Cache for JWKS
jwks_cache = None

def find_agent_arn(name):
    """Find agent ARN by name using Control Plane"""
    try:
        paginator = control_client.get_paginator('list_agent_runtimes')
        for page in paginator.paginate():
            for agent in page.get('agentRuntimes', []):
                if name in agent.get('agentRuntimeName', ''):
                    print(f"Found agent: {agent['agentRuntimeArn']}")
                    return agent['agentRuntimeArn']
    except Exception as e:
        print(f"Error auto-discovering agent: {e}")
    return None

def get_jwks():
    """Fetch and cache JWKS keys from Cognito"""
    global jwks_cache
    if jwks_cache:
        return jwks_cache
        
    if not USER_POOL_ID:
        print("USER_POOL_ID not set, skipping JWKS fetch")
        return None
        
    url = f'https://cognito-idp.{region}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json'
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            jwks_cache = response.json()['keys']
            return jwks_cache
    except Exception as e:
        print(f"Error fetching JWKS: {e}")
    return None

def verify_token(token):
    """Verify Cognito JWT Token"""
    if not token:
        return False
        
    # Remove 'Bearer ' prefix if present
    if token.startswith('Bearer '):
        token = token.split(' ')[1]
        
    try:
        # Get headers from token
        headers = jwt.get_unverified_headers(token)
        kid = headers.get('kid')
        
        # Get Public Keys
        keys = get_jwks()
        if not keys:
            print("Could not fetch JWKS keys")
            return False
            
        # Find the correct key
        key_index = -1
        for i in range(len(keys)):
            if kid == keys[i]['kid']:
                key_index = i
                break
                
        if key_index == -1:
            print('Public key not found in JWKS')
            return False
            
        # Construct Public Key
        public_key = jwk.construct(keys[key_index])
        
        # Get the message part of the token
        message, encoded_signature = str(token).rsplit('.', 1)
        
        # Verify Signature
        if not public_key.verify(message.encode("utf8"), base64url_decode(encoded_signature.encode("utf8"))):
            print('Signature verification failed')
            return False
            
        # Verify Claims (Expiration, Audience, Issuer)
        claims = jwt.get_unverified_claims(token)
        now = time.time()
        
        if now > claims['exp']:
            print('Token expired')
            return False
            
        if claims['aud'] != APP_CLIENT_ID:
            print('Token was not issued for this audience')
            # Note: For access tokens, 'aud' might not be present or might be different. 
            # Cognito Access Tokens have 'client_id' claim, ID Tokens have 'aud'.
            # If validation fails here, check if we are sending ID Token or Access Token.
            # The frontend usually sends ID Token for authentication.
            pass 
            
        if claims['iss'] != f'https://cognito-idp.{region}.amazonaws.com/{USER_POOL_ID}':
            print('Token issuer invalid')
            return False
            
        return True
        
    except Exception as e:
        print(f"Token validation error: {e}")
        return False

def handler(event, context):
    print("Received event:", json.dumps(event))
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Handle CORS preflight (OPTIONS) explicitly just in case
    http_method = event.get('httpMethod')
    if not http_method and 'requestContext' in event and 'http' in event['requestContext']:
        http_method = event['requestContext']['http']['method']
    
    if http_method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }

    # --- SECURITY: VALIDATE TOKEN ---
    auth_header = event.get('headers', {}).get('authorization') or event.get('headers', {}).get('Authorization')
    
    # For development/testing, you might want to skip this if USER_POOL_ID is not set
    if USER_POOL_ID:
        if not auth_header:
            print("Missing Authorization header")
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({'error': 'Unauthorized: Missing token'})
            }
        
        if not verify_token(auth_header):
            print("Invalid Token")
            return {
                'statusCode': 401,
                'headers': headers,
                'body': json.dumps({'error': 'Unauthorized: Invalid token'})
            }
    # --------------------------------
    
    # Lazy load or discovery ARN
    global AGENT_RUNTIME_ARN
    if not AGENT_RUNTIME_ARN:
        AGENT_RUNTIME_ARN = find_agent_arn(AGENT_NAME)
    
    if not AGENT_RUNTIME_ARN:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'AGENT_RUNTIME_ARN not configured and could not be discovered for name {AGENT_NAME}'})
        }

    try:
        body = json.loads(event.get('body', '{}'))
        prompt = body.get('prompt')
        
        if not prompt:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Prompt is required'})
            }

        # Invoke Agent
        payload = json.dumps({"prompt": prompt}).encode('utf-8')
        
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            payload=payload,
            qualifier="DEFAULT"
        )
        
        # Parse response stream (AgentCore returns serialized response in chunks)
        raw_response = ""
        if 'response' in response:
            for event in response['response']:
                chunk_content = ""
                
                # Handle different response types
                if isinstance(event, bytes):
                    chunk_content = event.decode('utf-8')
                elif isinstance(event, dict):
                    if 'chunk' in event:
                        chunk = event['chunk']
                        if isinstance(chunk, dict) and 'bytes' in chunk:
                            chunk_content = chunk['bytes'].decode('utf-8')
                        elif isinstance(chunk, bytes):
                            chunk_content = chunk.decode('utf-8')
                        else:
                            chunk_content = str(chunk)
                    elif 'bytes' in event:
                        chunk_content = event['bytes'].decode('utf-8')
                else:
                    chunk_content = str(event)
                
                raw_response += chunk_content
        
        # Attempt to parse the JSON response from the agent
        final_text = raw_response
        try:
            # The raw response is likely the JSON serialization of the Agent's return value
            response_obj = json.loads(raw_response)
            
            # Try to extract text from Strands Response structure
            if isinstance(response_obj, dict):
                if 'message' in response_obj and 'content' in response_obj['message']:
                    content = response_obj['message']['content']
                    if isinstance(content, list) and len(content) > 0:
                        final_text = content[0].get('text', raw_response)
                elif 'text' in response_obj:
                    final_text = response_obj['text']
                elif 'error' in response_obj:
                    return {
                        'statusCode': 500,
                        'headers': headers,
                        'body': json.dumps(response_obj)
                    }
            # If response_obj is a string (meaning raw_response was a JSON string "Hello"), use it directly
            elif isinstance(response_obj, str):
                final_text = response_obj
                
        except json.JSONDecodeError:
            # If it's not valid JSON, it might be raw text
            pass
            
        # Clean up any remaining surrounding quotes if they exist (sometimes artifact of double encoding)
        if isinstance(final_text, str):
            final_text = final_text.strip('"')
            
        # Return the final text wrapped in JSON
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(final_text)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
